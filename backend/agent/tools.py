"""
agent/tools.py — The 5 LangGraph tools for the HCP CRM agent.

Architecture note: We use a *factory* pattern (create_tools) rather than
module-level @tool decorators because each request needs tools that close
over:
  - `db`    — the SQLAlchemy session for this HTTP request
  - `state` — a mutable dict so tools can write back the interaction_id that
               the router then reads to fetch updated form data

The LangGraph ToolNode calls these functions, so their docstrings serve as
the tool descriptions the LLM sees when deciding which tool to invoke.
"""

import json
import os
import re
from datetime import date as dt_date
from typing import Optional

from langchain_core.tools import tool
from langchain_groq import ChatGroq


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_llm() -> ChatGroq:
    """Return the extraction LLM. Shared across all tool calls in a request."""
    model = os.getenv("AGENT_MODEL", "llama-3.3-70b-versatile")
    return ChatGroq(
        model=model,
        groq_api_key=os.getenv("GROQ_API_KEY"),
        temperature=0,
    )


def _parse_json(text: str) -> dict:
    """
    Robustly extract a JSON object from an LLM response.
    Handles markdown code fences (```json ... ```) that some models add.
    """
    # Strip markdown code fences
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fall back to regex search for the first {...} block
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group())
        raise ValueError(f"No valid JSON found in LLM response: {text[:300]}")


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------

def create_tools(db, state: dict) -> list:
    """
    Build the 5 LangGraph tools bound to a specific DB session and state dict.

    Parameters
    ----------
    db    : SQLAlchemy Session
    state : {"interaction_id": int | None}  — mutated by log_interaction so
            the router can fetch the updated form data after the agent runs.
    """
    from models import Interaction  # local import avoids circular import at startup

    llm = _get_llm()
    today = dt_date.today().isoformat()

    # ------------------------------------------------------------------
    # Tool 1 — log_interaction
    # ------------------------------------------------------------------
    @tool
    def log_interaction(description: str) -> str:
        """
        Log a new HCP (Healthcare Professional) interaction from a free-text description.

        Use this when the user describes a meeting, phone call, visit, email,
        or any interaction with a doctor or healthcare professional. Pass the
        user's full description as-is. The tool extracts structured fields
        (HCP name, date, topics, sentiment, etc.) and saves them to the database,
        then populates the form panel automatically.

        Example trigger phrases:
          "Today I met with Dr. Sharma and discussed..."
          "I had a call with Dr. Kapoor about..."
          "Log this interaction: ..."
        """
        extraction_prompt = f"""You are a pharma CRM data-extraction assistant.
Extract all details from the interaction description below and return ONLY a valid JSON object.

Today's date: {today}

JSON fields (use null for missing string fields, [] for missing list fields):
{{
  "hcp_name": "Full name of the Healthcare Professional",
  "interaction_type": "One of: Meeting, Phone Call, Email, Conference, Webinar, Product Detail",
  "date": "YYYY-MM-DD (use {today} if not mentioned)",
  "time": "HH:MM 24-hour format or null",
  "attendees": ["list of people present besides the HCP"],
  "topics_discussed": ["specific products, diseases, or topics covered"],
  "materials_shared": ["brochures, PDFs, or documents handed over"],
  "samples_distributed": ["product samples distributed"],
  "sentiment": "Exactly one of: Positive, Neutral, Negative",
  "outcomes": "Brief summary of what was decided or agreed upon",
  "follow_up_actions": ["specific follow-up tasks planned"]
}}

Interaction description:
{description}

Return ONLY the JSON object, no other text:"""

        response = llm.invoke(extraction_prompt)

        try:
            data = _parse_json(response.content)
        except (ValueError, json.JSONDecodeError) as exc:
            return (
                f"I had trouble parsing the interaction details: {exc}. "
                "Could you rephrase or provide more details?"
            )

        # Persist to DB
        interaction = Interaction(
            hcp_name=data.get("hcp_name"),
            interaction_type=data.get("interaction_type"),
            date=data.get("date", today),
            time=data.get("time"),
            attendees=data.get("attendees") or [],
            topics_discussed=data.get("topics_discussed") or [],
            materials_shared=data.get("materials_shared") or [],
            samples_distributed=data.get("samples_distributed") or [],
            sentiment=data.get("sentiment"),
            outcomes=data.get("outcomes"),
            follow_up_actions=data.get("follow_up_actions") or [],
        )
        db.add(interaction)
        db.commit()
        db.refresh(interaction)

        # Write ID back into shared state so the router can fetch form data
        state["interaction_id"] = interaction.id

        # Build a human-friendly summary
        parts = []
        if interaction.hcp_name:
            parts.append(f"HCP: {interaction.hcp_name}")
        if interaction.interaction_type:
            parts.append(f"Type: {interaction.interaction_type}")
        if interaction.date:
            parts.append(f"Date: {interaction.date}")
        if interaction.topics_discussed:
            parts.append(f"Topics: {', '.join(interaction.topics_discussed)}")
        if interaction.sentiment:
            parts.append(f"Sentiment: {interaction.sentiment}")

        summary = " | ".join(parts) if parts else "details saved"
        return (
            f"Interaction logged successfully (ID: {interaction.id}).\n"
            f"{summary}\n\n"
            "The form panel has been updated. "
            "Would you like me to suggest follow-ups, check compliance, or recommend materials for the next visit?"
        )

    # ------------------------------------------------------------------
    # Tool 2 — edit_interaction
    # ------------------------------------------------------------------
    @tool
    def edit_interaction(correction: str) -> str:
        """
        Correct or update specific fields in the currently logged interaction.

        Use this when the user says something was wrong or wants to change a
        specific detail — without re-logging the entire interaction. Only the
        fields explicitly mentioned in the correction will be updated; everything
        else stays the same.

        Example trigger phrases:
          "Actually, the doctor's name is Dr. John, not Dr. Smith"
          "The sentiment was negative, not positive"
          "Add 'brochure X' to the materials shared"
          "Change the date to 2024-06-15"
        """
        interaction_id = state.get("interaction_id")
        if not interaction_id:
            return (
                "No interaction has been logged yet. "
                "Please describe your HCP interaction first so I can log it."
            )

        interaction = db.query(Interaction).filter(Interaction.id == interaction_id).first()
        if not interaction:
            return f"Could not find interaction #{interaction_id}. Please describe the interaction again."

        current = json.dumps(interaction.to_dict(), indent=2)

        edit_prompt = f"""You are a pharma CRM data-correction assistant.
Given the CURRENT interaction data and a USER CORRECTION, determine which fields need updating.
Return ONLY a JSON object containing the fields that MUST CHANGE based on the correction.
Do NOT include fields that stay the same.

Current interaction data:
{current}

User correction:
{correction}

Return ONLY a JSON object with the fields to update (use the same field names):"""

        response = llm.invoke(edit_prompt)

        try:
            updates = _parse_json(response.content)
        except (ValueError, json.JSONDecodeError) as exc:
            return f"Could not parse the correction: {exc}. Please try rephrasing."

        # Apply only the fields that are present in the update dict
        editable_fields = [
            "hcp_name", "interaction_type", "date", "time",
            "attendees", "topics_discussed", "materials_shared",
            "samples_distributed", "sentiment", "outcomes", "follow_up_actions",
        ]
        changed = []
        for field in editable_fields:
            if field in updates and updates[field] is not None:
                setattr(interaction, field, updates[field])
                changed.append(field.replace("_", " ").title())

        if not changed:
            return (
                "I couldn't identify any specific fields to change from your correction. "
                "Could you be more explicit? For example: 'Change the HCP name to Dr. Rao' "
                "or 'Set sentiment to Negative'."
            )

        db.commit()
        db.refresh(interaction)

        return (
            f"Updated: {', '.join(changed)}.\n"
            "The form panel reflects the new values. Anything else to correct?"
        )

    # ------------------------------------------------------------------
    # Tool 3 — suggest_follow_ups
    # ------------------------------------------------------------------
    @tool
    def suggest_follow_ups() -> str:
        """
        Generate AI-powered, context-aware follow-up suggestions for the current interaction.

        Use this when the user asks what to do next, wants follow-up ideas, or
        asks for next steps after the interaction. Suggestions are tailored to
        the specific HCP, topics discussed, and the HCP's sentiment. Results are
        written into the 'AI Suggested Follow-ups' section of the form.

        Example trigger phrases:
          "What follow-ups should I schedule?"
          "Suggest next steps"
          "What should I do after this meeting?"
        """
        interaction_id = state.get("interaction_id")
        if not interaction_id:
            return "No interaction logged yet. Please log the interaction first."

        interaction = db.query(Interaction).filter(Interaction.id == interaction_id).first()
        if not interaction:
            return "Could not find the current interaction."

        context = f"""
HCP: {interaction.hcp_name or 'Unknown'}
Interaction Type: {interaction.interaction_type or 'Unknown'}
Date: {interaction.date or 'Unknown'}
Topics Discussed: {', '.join(interaction.topics_discussed or []) or 'None recorded'}
Materials Shared: {', '.join(interaction.materials_shared or []) or 'None'}
Samples Distributed: {', '.join(interaction.samples_distributed or []) or 'None'}
HCP Sentiment: {interaction.sentiment or 'Unknown'}
Outcomes: {interaction.outcomes or 'None recorded'}
Existing Follow-ups: {', '.join(interaction.follow_up_actions or []) or 'None'}
"""

        prompt = f"""You are an expert pharmaceutical field-rep coach.
Based on this HCP interaction, generate 4-5 specific and actionable follow-up suggestions.

Consider: scheduling follow-up calls or visits, sending clinical study PDFs, inviting to
upcoming webinars or symposiums, providing sample replenishment, submitting expense/sample
reports, sharing patient support program info, addressing raised concerns, or escalating to a KOL.

Make each suggestion concrete — include the HCP name, a timeline, and a specific action.
Bad: "Schedule a call" — Good: "Schedule a 20-min follow-up call with Dr. Sharma in 2 weeks to share the updated efficacy data from the CLARITY trial."

Interaction context:
{context}

Return ONLY a JSON object:
{{"suggestions": ["suggestion 1", "suggestion 2", "suggestion 3", "suggestion 4", "suggestion 5"]}}"""

        response = llm.invoke(prompt)

        try:
            result = _parse_json(response.content)
            suggestions = result.get("suggestions", [])
        except (ValueError, json.JSONDecodeError):
            suggestions = [
                f"Schedule a follow-up visit with {interaction.hcp_name or 'the HCP'} in 2 weeks",
                "Send the clinical study summary via email within 48 hours",
                "Submit a sample replenishment request through the portal",
                "Add the HCP to the upcoming regional symposium invite list",
            ]

        interaction.ai_suggested_follow_ups = suggestions
        db.commit()

        bullets = "\n".join(f"• {s}" for s in suggestions)
        return (
            f"Here are AI-suggested follow-ups for {interaction.hcp_name or 'this HCP'}:\n\n"
            f"{bullets}\n\n"
            "These have been added to the 'AI Suggested Follow-ups' section of the form."
        )

    # ------------------------------------------------------------------
    # Tool 4 — check_compliance
    # ------------------------------------------------------------------
    @tool
    def check_compliance() -> str:
        """
        Check the current interaction for pharma industry compliance issues.

        Use this when the user wants to verify the interaction follows regulatory
        and industry guidelines — e.g., PhRMA Code, PDMA, off-label promotion
        rules, sample documentation requirements, or consent obligations.
        Results are saved to the compliance notes field of the form.

        Example trigger phrases:
          "Is this interaction compliant?"
          "Check for compliance issues"
          "Are there any regulatory concerns?"
          "Did I do anything I shouldn't have?"
        """
        interaction_id = state.get("interaction_id")
        if not interaction_id:
            return "No interaction logged yet. Please log the interaction first."

        interaction = db.query(Interaction).filter(Interaction.id == interaction_id).first()
        if not interaction:
            return "Could not find the current interaction."

        context = f"""
Interaction Type: {interaction.interaction_type or 'Unknown'}
Topics Discussed: {', '.join(interaction.topics_discussed or []) or 'None'}
Materials Shared: {', '.join(interaction.materials_shared or []) or 'None'}
Samples Distributed: {', '.join(interaction.samples_distributed or []) or 'None'}
Outcomes: {interaction.outcomes or 'None'}
"""

        prompt = f"""You are a pharma compliance expert reviewing a field-rep's HCP interaction.
Check for potential issues against these standards:
1. Off-label promotion (discussing unapproved indications)
2. Sample documentation requirements (PDMA — samples must be signed for)
3. PhRMA Code — meals/gifts must be modest, educational, not entertainment
4. Consent requirements (recording conversations, collecting personal data)
5. Adverse event (AE) reporting obligations
6. Transparency / Sunshine Act reporting for transfers of value

Interaction details:
{context}

Return ONLY a JSON object:
{{
  "status": "Clear | Warning | Action Required",
  "issues": ["specific issue 1 or 'None identified'"],
  "recommendations": ["specific recommended action 1"]
}}"""

        response = llm.invoke(prompt)

        try:
            result = _parse_json(response.content)
            status = result.get("status", "Clear")
            issues = result.get("issues", ["None identified"])
            recommendations = result.get("recommendations", [])
        except (ValueError, json.JSONDecodeError):
            status = "Clear"
            issues = ["Unable to analyze automatically — review manually"]
            recommendations = ["Consult your compliance officer"]

        note = (
            f"Status: {status}\n\n"
            f"Issues:\n" + "\n".join(f"  • {i}" for i in issues)
        )
        if recommendations:
            note += "\n\nRecommended Actions:\n" + "\n".join(f"  • {r}" for r in recommendations)

        interaction.compliance_notes = note
        db.commit()

        return note

    # ------------------------------------------------------------------
    # Tool 5 — recommend_materials
    # ------------------------------------------------------------------
    @tool
    def recommend_materials(specialty: Optional[str] = None) -> str:
        """
        Recommend clinical materials, brochures, or resources to share with the HCP
        at the next visit, based on the current interaction context.

        Use this when the user wants to know what to bring next time, which clinical
        studies are relevant, or what resources would address the HCP's interests or
        concerns. Optionally pass the HCP's medical specialty for targeted suggestions.
        Results are stored in the 'Recommended Materials' field.

        Example trigger phrases:
          "What materials should I bring next time?"
          "Recommend relevant clinical studies"
          "What resources would Dr. Kapoor find useful?"
          "What should I send after this meeting?"

        Args:
            specialty: Optional HCP medical specialty (e.g., "Cardiologist", "Oncologist")
        """
        interaction_id = state.get("interaction_id")
        if not interaction_id:
            return "No interaction logged yet. Please log the interaction first."

        interaction = db.query(Interaction).filter(Interaction.id == interaction_id).first()
        if not interaction:
            return "Could not find the current interaction."

        context = f"""
HCP: {interaction.hcp_name or 'Unknown'}
Medical Specialty: {specialty or 'Not specified'}
Topics Discussed: {', '.join(interaction.topics_discussed or []) or 'None'}
HCP Sentiment: {interaction.sentiment or 'Unknown'}
Outcomes: {interaction.outcomes or 'None'}
Already Shared: {', '.join(interaction.materials_shared or []) or 'Nothing yet'}
"""

        prompt = f"""You are a pharma medical affairs expert recommending materials for a field rep.
Suggest 4-5 specific materials relevant to this HCP interaction. Avoid repeating what's already been shared.

Material types to consider: Phase III clinical trial summaries, mechanism-of-action slides,
head-to-head comparison charts, patient case studies, disease-state awareness brochures,
adherence support program guides, formulary coverage sheets, patient savings card info,
continuing medical education (CME) resources.

Context:
{context}

Return ONLY a JSON object:
{{
  "recommended_materials": [
    {{"title": "...", "type": "...", "reason": "one sentence on why it's relevant"}}
  ]
}}"""

        response = llm.invoke(prompt)

        try:
            result = _parse_json(response.content)
            materials = result.get("recommended_materials", [])
        except (ValueError, json.JSONDecodeError):
            materials = [
                {"title": "Product Efficacy Overview", "type": "Brochure", "reason": "Core product messaging"},
                {"title": "Phase III Trial Summary", "type": "Clinical Study", "reason": "Evidence to support discussions"},
            ]

        # Persist as a simple list of strings
        material_strings = [
            f"{m.get('title', 'Unknown')} ({m.get('type', 'Material')})"
            for m in materials
        ]
        interaction.recommended_materials = material_strings
        db.commit()

        lines = [
            f"• {m.get('title')} [{m.get('type')}] — {m.get('reason', '')}"
            for m in materials
        ]
        return (
            f"Recommended materials for the next visit with {interaction.hcp_name or 'this HCP'}:\n\n"
            + "\n".join(lines)
            + "\n\nThese have been saved to the form under 'Recommended Materials'."
        )

    return [
        log_interaction,
        edit_interaction,
        suggest_follow_ups,
        check_compliance,
        recommend_materials,
    ]
