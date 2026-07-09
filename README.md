# AI-First HCP CRM — Log Interaction Screen

> Pharma field reps describe a doctor visit in plain English via chat. A LangGraph ReAct agent extracts structured CRM data, checks pharma compliance, suggests follow-ups, and recommends clinical materials — all automatically.

**The form is never filled manually. The only way to populate it is through the AI chat.**

> **Note on LLM model:** The assignment specifies `gemma2-9b-it` via Groq. This model was **decommissioned by Groq in July 2026** and is no longer available. The implementation uses `llama-3.1-8b-instant` as a drop-in replacement (same provider, same tool-calling support). To switch models, change `AGENT_MODEL` in `backend/.env`.

---

## Screenshots

**Empty screen — form and chat ready**

![Empty form](screenshots/01_empty_form.png)

**After logging — AI fills every field from the chat entry**

![Form filled by AI](screenshots/02_form_filled.png)

---

## How It Works — End to End

```mermaid
sequenceDiagram
    participant Rep as Field Rep (Browser)
    participant Redux as Redux Store
    participant API as FastAPI Backend
    participant Agent as LangGraph Agent
    participant Tool as @tool (e.g. log_interaction)
    participant LLM as Groq LLM
    participant DB as PostgreSQL

    Rep->>Redux: Types log entry in chat · clicks Log
    Redux->>Redux: Adds user message to chat (immediate)
    Redux->>API: POST /api/chat · { message, interaction_id, history }

    API->>API: Creates agent_state { interaction_id }
    API->>API: create_tools(db, agent_state) — 5 tool closures
    API->>Agent: agent.invoke(messages)

    Agent->>LLM: Router LLM — reads message + tool descriptions
    LLM-->>Agent: Decides to call log_interaction

    Agent->>Tool: log_interaction(description)
    Tool->>LLM: Extraction LLM — NLP → structured JSON
    LLM-->>Tool: { hcp_name, date, topics, sentiment, outcomes, ... }
    Tool->>DB: INSERT INTO interactions → gets id = 7
    Tool-->>Agent: "Interaction logged (ID 7). HCP: Dr. Sharma | Sentiment: Positive ..."

    Agent->>LLM: Router LLM — anything else to do?
    LLM-->>Agent: No tool calls — compose final reply
    Agent-->>API: "✅ Interaction logged successfully! ..."

    API->>DB: SELECT * FROM interactions WHERE id = 7
    DB-->>API: Full row (14 fields)
    API-->>Redux: { message, interaction_id: 7, form_data }

    Redux->>Rep: AI reply appears in chat
    Redux->>Rep: Form panel populates with all 14 fields
```

---

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Frontend | React 18 + Vite | Split-screen layout, Google Inter font |
| State | Redux Toolkit | `interactionSlice` (form) + `chatSlice` (chat + thunk) |
| Backend | FastAPI 0.139 | Dependency injection, auto DB table creation on startup |
| AI Orchestration | LangGraph 1.2.8 | ReAct loop — agent node ↔ tools node |
| LLM | Groq — llama-3.1-8b-instant | Fast inference, tool-calling support |
| Database | PostgreSQL + SQLAlchemy 2 | JSONB columns for list fields |
| Package Manager | uv | Reproducible lockfile, 10× faster than pip |
| Containerisation | Docker + Docker Compose | One-command setup — postgres + backend + frontend |
| Reverse Proxy | nginx (Alpine) | Serves built React app, proxies `/api` to FastAPI |

---

## The 5 LangGraph Tools

| # | Tool | What it does | Triggered when rep says |
|---|------|-------------|-----------------|
| 1 | `log_interaction` | Extracts all 14 form fields from the chat entry → INSERT to DB | *"Today I met Dr. Priya Sharma at Apollo…"* |
| 2 | `edit_interaction` | Differential update — changes only the mentioned fields, keeps everything else | *"Actually the sentiment was Neutral, not Positive"* |
| 3 | `suggest_follow_ups` | Generates 4–5 HCP-specific, time-bound follow-up actions | *"Suggest follow-ups for this visit"* |
| 4 | `check_compliance` | Audits against PhRMA Code, PDMA sample rules, Sunshine Act | *"Is this interaction compliant?"* |
| 5 | `recommend_materials` | Suggests clinical materials for the next visit; skips what was already shared | *"What should I bring to Dr. Sharma next time?"* |

**Why LangGraph instead of a simple LLM call?**

The ReAct loop means the LLM sees tool results and keeps reasoning. This enables:
- **Chaining**: "Check compliance and suggest follow-ups" → agent calls both tools in sequence
- **Selective use**: A general question triggers no tool — no wasted DB writes
- **Semantic routing**: The LLM reads tool docstrings to decide — not keyword matching

---

## Project Structure

```
ai-hcp-crm/
├── docker-compose.yml             # Run everything with one command
├── .env.example                   # Environment variable template
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml             # uv dependencies
│   ├── requirements.txt           # pip fallback
│   ├── .env.example
│   ├── main.py                    # FastAPI app + DB table creation on startup
│   ├── database.py                # SQLAlchemy engine + session
│   ├── models.py                  # Interaction + ChatMessage ORM models
│   ├── schemas.py                 # Pydantic request/response schemas
│   ├── agent/
│   │   ├── graph.py               # LangGraph StateGraph (ReAct loop)
│   │   └── tools.py               # 5 tools via factory pattern
│   └── routers/
│       └── interactions.py        # POST /api/chat endpoint
│
└── frontend/
    ├── Dockerfile
    ├── nginx.conf                 # Proxies /api to backend in Docker
    ├── index.html
    ├── package.json
    ├── vite.config.js             # Proxies /api → localhost:8000 in dev
    └── src/
        ├── App.jsx                # Split-screen layout + message handler
        ├── App.css                # Viewport lock, panel flex layout
        ├── store/
        │   └── slices/
        │       ├── interactionSlice.js   # Form state — read-only, AI writes only
        │       └── chatSlice.js          # Messages, loading state, sendMessage thunk
        └── components/
            ├── FormPanel/         # Left panel — all fields are readOnly
            └── ChatPanel/         # Right panel — input + AI chat bubbles
```

---

## Prerequisites

| Tool | Version |
|------|---------|
| Docker + Docker Compose | Any recent version |
| Groq API key | Free at [console.groq.com](https://console.groq.com) |

---

## Run with Docker (recommended)

```bash
git clone https://github.com/Kanchan95/ai-hcp-crm.git
cd ai-hcp-crm

cp .env.example .env
# Open .env and paste your GROQ_API_KEY

docker compose up --build
```

Open `http://localhost:3000`

---

## Run Locally (without Docker)

### 1. Create the PostgreSQL database

```bash
psql -U postgres -c "CREATE DATABASE hcp_crm;"
```

### 2. Backend

```bash
cd backend

uv venv --python 3.11
source .venv/bin/activate
uv pip install -e "."

cp .env.example .env
# Set GROQ_API_KEY and DATABASE_URL in .env

uvicorn main:app --reload --port 8000
```

**Alternative (pip):**
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` · API docs at `http://localhost:8000/docs`

### Environment Variables (`backend/.env`)

```env
GROQ_API_KEY=gsk_...
DATABASE_URL=postgresql://postgres:password@localhost:5432/hcp_crm
AGENT_MODEL=llama-3.1-8b-instant
```

---

## Key Design Decisions

**Form is 100% read-only** — Every `<input>` and `<textarea>` has `readOnly`/`disabled`. No `onChange` handlers exist. The only write path is `dispatch(updateInteraction(form_data))` triggered by an API response.

**Factory pattern for tools** — `create_tools(db, state)` creates 5 tool closures per HTTP request. Each closure captures the same SQLAlchemy session and the same mutable `agent_state` dict, so `log_interaction` can write the new `interaction_id` back for the router to read after the graph finishes.

**Two LLM calls per tool** — The Router LLM (agent node) only decides which tool to call. The Extraction LLM runs inside each tool with a focused NLP prompt. This keeps each call small and accurate.

**Scroll isolation** — `html, body, #root { overflow: hidden }` locks the page. Chat scrolls via `messagesRef.scrollTop = scrollHeight`. FormPanel uses `useLayoutEffect` to restore scroll position across Redux re-renders so the form never jumps when AI populates it.

**History capped at 4 turns** — Only the last 8 messages are sent per request, keeping usage within Groq's free tier (100k tokens/day).

---

## Author

**Kanchan Chowdhary**
kanchan.chowdhary95@gmail.com
Full-Stack Engineer | Bengaluru
