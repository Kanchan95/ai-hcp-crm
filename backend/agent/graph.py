"""
agent/graph.py — LangGraph ReAct agent definition for the HCP CRM.

Architecture: Standard ReAct (Reasoning + Acting) loop.
  - "agent" node: The LLM decides which tool to call (or responds directly).
  - "tools" node: LangGraph's ToolNode executes the chosen tool.
  - Loop until the LLM's last message has no tool_calls → END.

This is the canonical LangGraph pattern. We build the graph manually (rather
than using create_react_agent) to keep the system prompt flexible per request.
"""

import os
from typing import TypedDict, Annotated, Sequence

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode


class AgentState(TypedDict):
    """State that flows through every node in the LangGraph."""
    messages: Annotated[Sequence[BaseMessage], add_messages]


def create_hcp_agent(tools: list, interaction_id=None):
    """
    Compile and return a LangGraph agent app for one HTTP request.

    Parameters
    ----------
    tools          : list of LangChain @tool functions (created by agent/tools.py)
    interaction_id : current interaction ID or None — injected into the system prompt
                     so the LLM always has context about what's been logged so far.
    """
    model_name = os.getenv("AGENT_MODEL", "llama-3.3-70b-versatile")
    llm = ChatGroq(
        model=model_name,
        groq_api_key=os.getenv("GROQ_API_KEY"),
        temperature=0,
    )
    # Bind the tools so the LLM knows their signatures / when to call them
    llm_with_tools = llm.bind_tools(tools)

    system_content = f"""You are an AI assistant embedded in a pharma CRM for field medical representatives.
Your job is to help reps log and manage their HCP (Healthcare Professional) interactions.

Current Interaction ID in session: {interaction_id if interaction_id else "None — not logged yet"}

You have exactly 5 tools:
1. log_interaction   — Parse a natural-language description and populate the interaction form
2. edit_interaction  — Correct or update specific fields based on a user correction
3. suggest_follow_ups — Generate smart follow-up recommendations for this HCP
4. check_compliance  — Flag any pharma compliance issues with the interaction
5. recommend_materials — Suggest relevant clinical materials for the next visit

Decision rules:
• User describes a meeting / call / visit → call log_interaction
• User says "actually...", "the name was...", "change..." → call edit_interaction
• User asks "what next?", "follow-up?", "next steps?" → call suggest_follow_ups
• User mentions compliance, off-label, gifts, samples → call check_compliance
• User asks "what to bring?", "which studies?", "what materials?" → call recommend_materials

After every tool call, give a brief, friendly confirmation of what changed.
If something is unclear, ask one clarifying question.
Stay professional and concise."""

    tool_node = ToolNode(tools)

    def agent_node(state: AgentState) -> dict:
        """Call the LLM. Prepend the system message if it's not already there."""
        messages = list(state["messages"])
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_content)] + messages
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        """Route: if the last message has tool_calls → execute them; otherwise finish."""
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return "end"

    # Build the graph
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "end": END},
    )
    graph.add_edge("tools", "agent")

    return graph.compile()
