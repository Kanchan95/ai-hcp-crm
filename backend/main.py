"""
main.py — FastAPI application entry point for the HCP CRM backend.

Start with:
    uvicorn main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers.interactions import router as interactions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup (replaces deprecated @app.on_event)."""
    init_db()
    print("✅ HCP CRM backend started. Tables initialized.")
    yield  # app runs here


app = FastAPI(
    title="HCP CRM — AI Interaction Logger",
    description="AI-first CRM backend for pharma field reps powered by LangGraph + Groq.",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow the Vite dev server (port 3000) during development.
# In production, restrict this to your actual frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(interactions_router)
