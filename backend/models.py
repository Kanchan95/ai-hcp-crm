"""
models.py — SQLAlchemy ORM models for the HCP CRM.

Two tables:
  - interactions: stores one form's worth of HCP interaction data
  - chat_messages: audit log of all user/AI messages per interaction
"""

import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from database import Base


class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)

    # Core form fields (all nullable — filled progressively by the AI)
    hcp_name = Column(String(255), nullable=True)
    interaction_type = Column(String(100), nullable=True)  # Meeting, Call, Email, etc.
    date = Column(String(20), nullable=True)               # YYYY-MM-DD string
    time = Column(String(10), nullable=True)               # HH:MM string
    attendees = Column(JSONB, default=list)
    topics_discussed = Column(JSONB, default=list)
    materials_shared = Column(JSONB, default=list)
    samples_distributed = Column(JSONB, default=list)
    sentiment = Column(String(20), nullable=True)          # Positive | Neutral | Negative
    outcomes = Column(Text, nullable=True)
    follow_up_actions = Column(JSONB, default=list)

    # AI-enriched fields (written by the LangGraph tools)
    ai_suggested_follow_ups = Column(JSONB, default=list)
    compliance_notes = Column(Text, nullable=True)
    recommended_materials = Column(JSONB, default=list)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON responses and tool use."""
        return {
            "id": self.id,
            "hcp_name": self.hcp_name,
            "interaction_type": self.interaction_type,
            "date": self.date,
            "time": self.time,
            "attendees": self.attendees or [],
            "topics_discussed": self.topics_discussed or [],
            "materials_shared": self.materials_shared or [],
            "samples_distributed": self.samples_distributed or [],
            "sentiment": self.sentiment,
            "outcomes": self.outcomes,
            "follow_up_actions": self.follow_up_actions or [],
            "ai_suggested_follow_ups": self.ai_suggested_follow_ups or [],
            "compliance_notes": self.compliance_notes,
            "recommended_materials": self.recommended_materials or [],
        }


class ChatMessage(Base):
    """Audit log — every user and assistant message is stored here."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    interaction_id = Column(Integer, nullable=True)   # FK-like, nullable before first log_interaction
    role = Column(String(20))                          # "user" or "assistant"
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
