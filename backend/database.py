"""
database.py — SQLAlchemy engine, session factory, and DB initializer.

Design decision: We use a synchronous SQLAlchemy session (not async) because
LangGraph tools run synchronously inside the agent loop. Mixing async/sync
SQLAlchemy sessions across tool calls is error-prone in a prototype; sync is
simpler and correct here.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/hcp_crm",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables defined under Base. Called once at app startup."""
    # Import models here so SQLAlchemy registers them with Base.metadata
    import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
