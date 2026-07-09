"""
schemas.py — Pydantic request/response models for the FastAPI layer.

These are separate from the SQLAlchemy models to keep the API contract
independent of the DB schema (useful when the two diverge during iteration).
"""

from pydantic import BaseModel
from typing import Optional, List


class HistoryMessage(BaseModel):
    role: str    # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    interaction_id: Optional[int] = None          # None until first log_interaction call
    history: Optional[List[HistoryMessage]] = []  # Recent conversation turns for context


class ChatResponse(BaseModel):
    message: str                         # AI assistant's text reply shown in the chat panel
    interaction_id: Optional[int] = None # Returned so the frontend can store it in Redux
    form_data: Optional[dict] = None     # Full interaction dict to update the form panel
