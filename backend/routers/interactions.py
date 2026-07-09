"""
routers/interactions.py — FastAPI endpoints for the HCP CRM.

POST /api/chat      — Main endpoint. Runs the LangGraph agent and returns
                      the AI message + updated form data.
GET  /api/interactions/{id} — Fetch a specific interaction by ID.
DELETE /api/interactions/{id} — Delete an interaction (reset the form).
GET  /api/health    — Basic liveness probe.
"""

import traceback

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import HumanMessage, AIMessage
from sqlalchemy.orm import Session

from database import get_db
from models import ChatMessage, Interaction
from schemas import ChatRequest, ChatResponse
from agent.tools import create_tools
from agent.graph import create_hcp_agent

router = APIRouter(prefix="/api", tags=["interactions"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Main conversational endpoint.

    Flow:
      1. Create a mutable `agent_state` dict — tools write the interaction_id back here.
      2. Create the 5 tools (closures over db + agent_state).
      3. Build and run the LangGraph agent with the conversation history.
      4. After the agent finishes, read agent_state["interaction_id"] to know which
         DB record was created/updated, then fetch and return the full form data.
      5. Persist both the user message and AI response to chat_messages for audit.
    """
    try:
        # Shared mutable state between this request and the tools
        agent_state = {"interaction_id": request.interaction_id}

        tools = create_tools(db, agent_state)
        agent = create_hcp_agent(tools, interaction_id=request.interaction_id)

        # Keep last 4 turns (8 messages) — enough context, saves ~50% tokens on free tier
        history_msgs = []
        for msg in (request.history or [])[-4:]:
            if msg.role == "user":
                history_msgs.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                history_msgs.append(AIMessage(content=msg.content))

        history_msgs.append(HumanMessage(content=request.message))

        # ---- Run the LangGraph agent ----
        result = agent.invoke({"messages": history_msgs})

        # The last message is the final AI text response
        final_msg = result["messages"][-1]
        ai_text = (
            final_msg.content
            if hasattr(final_msg, "content")
            else str(final_msg)
        )

        # Resolve the interaction ID (may have been set by log_interaction tool)
        resolved_id = agent_state.get("interaction_id")

        # Fetch updated form data if we have an interaction
        form_data = None
        if resolved_id:
            interaction = (
                db.query(Interaction)
                .filter(Interaction.id == resolved_id)
                .first()
            )
            if interaction:
                form_data = interaction.to_dict()

        # Audit: persist chat messages
        db.add(ChatMessage(
            interaction_id=resolved_id,
            role="user",
            content=request.message,
        ))
        db.add(ChatMessage(
            interaction_id=resolved_id,
            role="assistant",
            content=ai_text,
        ))
        db.commit()

        return ChatResponse(
            message=ai_text,
            interaction_id=resolved_id,
            form_data=form_data,
        )

    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="The AI agent encountered an error. Check the server logs.",
        )


@router.get("/interactions/{interaction_id}")
def get_interaction(interaction_id: int, db: Session = Depends(get_db)):
    """Return a single interaction by its database ID."""
    row = db.query(Interaction).filter(Interaction.id == interaction_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Interaction not found")
    return row.to_dict()


@router.delete("/interactions/{interaction_id}")
def delete_interaction(interaction_id: int, db: Session = Depends(get_db)):
    """Delete an interaction record (used by the frontend 'New Interaction' button)."""
    row = db.query(Interaction).filter(Interaction.id == interaction_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Interaction not found")
    db.delete(row)
    db.commit()
    return {"message": "Interaction deleted"}


@router.get("/health")
def health():
    return {"status": "ok"}
