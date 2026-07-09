# AI-First HCP CRM — Log Interaction Screen

> Pharma field reps describe a doctor visit in plain English. A LangGraph ReAct agent extracts structured CRM data, checks pharma compliance, suggests follow-ups, and recommends clinical materials — all automatically.

**The form is never filled manually. The AI fills it exclusively through the chat.**

> **Note on LLM model:** The assignment specifies `gemma2-9b-it` via Groq. This model was **decommissioned by Groq in July 2026** and is no longer available on the platform. The implementation uses `llama-3.1-8b-instant` as a drop-in replacement (same provider, same tool-calling support). To switch models, change `AGENT_MODEL` in `backend/.env`. `llama-3.3-70b-versatile` (also specified in the assignment) works as well — it hits the 100k token/day free-tier limit faster but produces higher-quality output.

---

## Demo

### Screenshots

**Before — empty form, chat ready**

![Empty form](screenshots/01_empty_form.png)

**After — AI fills every field from one natural language message**

![Form filled by AI](screenshots/02_form_filled.png)

---

## System Architecture

```mermaid
flowchart TB
    Browser["🖥️ BROWSER\nReact 18 + Redux Toolkit + Vite\nFormPanel left read-only · ChatPanel right input"]
    FastAPI["⚡ FASTAPI BACKEND\nPOST /api/chat\ncreate_tools(db, state) → agent.invoke()"]
    LangGraph["🔁 LANGGRAPH ReAct AGENT\nagent node ↔ tools node\nStateGraph · ToolNode · add_messages"]
    Tools["🛠️ 5 TOOLS\nlog_interaction · edit_interaction\nsuggest_follow_ups · check_compliance · recommend_materials"]
    Groq["🤖 GROQ CLOUD\nllama-3.1-8b-instant\nRouter LLM + Extraction LLM per tool"]
    PG["🗄️ POSTGRESQL\ninteractions table · 14 cols · JSONB list fields\nchat_messages table · full audit log"]

    Browser -->|"POST /api/chat + history"| FastAPI
    FastAPI -->|"agent.invoke(messages)"| LangGraph
    LangGraph -->|"tool_calls"| Tools
    Tools <-->|"NLP extraction via 2nd LLM call"| Groq
    Tools -->|"INSERT / UPDATE"| PG
    PG -->|"form_data"| FastAPI
    FastAPI -->|"message + form_data"| Browser
```

---

## LangGraph ReAct Agent Flow

```mermaid
flowchart LR
    Start(["💬 User Message"])
    Agent["Agent Node\n─────────────────\nPrepend SystemMessage\nllm.bind_tools().invoke()\nLLM reads docstrings\nDecides which tool to call"]
    ToolsNode["Tools Node\n─────────────────\nFinds @tool by name\nCalls with LLM args\n2nd LLM extracts JSON\nWrites to PostgreSQL\nReturns ToolMessage"]
    End(["✅ AI Response\n+ form_data\nreturned to frontend"])

    Start --> Agent
    Agent -->|"has tool_calls"| ToolsNode
    ToolsNode -->|"ToolMessage · loop back"| Agent
    Agent -->|"no tool_calls → END"| End
```

> The LLM reads tool docstrings to decide which tool to call — no hardcoded routing or keyword matching.

---

## End-to-End Data Flow

```mermaid
sequenceDiagram
    participant U as User Browser
    participant R as Redux
    participant F as FastAPI
    participant L as LangGraph Agent
    participant T as Tool
    participant G as Groq LLM
    participant P as PostgreSQL

    U->>R: Type message · click Log
    R->>R: addUserMessage optimistic UI
    R->>F: POST /api/chat with message and history
    F->>F: create agent_state and create_tools
    F->>L: agent.invoke messages
    L->>G: Router LLM — which tool?
    G-->>L: tool_calls log_interaction
    L->>T: execute log_interaction description
    T->>G: Extraction LLM — NLP to JSON
    G-->>T: hcp_name · topics · sentiment · outcomes
    T->>P: INSERT INTO interactions
    P-->>T: interaction_id = 7
    T-->>L: ToolMessage success
    L->>G: Router LLM — anything else?
    G-->>L: no tool_calls END
    L-->>F: final AI text
    F->>P: SELECT all fields WHERE id = 7
    P-->>F: full form_data 14 fields
    F-->>R: message + interaction_id + form_data
    R->>U: updateInteraction → form populates
```

---

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Frontend | React 18 + Vite | Split-screen layout, Inter font |
| State | Redux Toolkit | Two slices: `interactionSlice` (form) + `chatSlice` (chat) |
| Backend | FastAPI 0.139 | Async, dependency injection, OpenAPI docs |
| AI Orchestration | LangGraph 1.2.8 | ReAct loop — agent node ↔ tools node |
| LLM | Groq (llama-3.1-8b-instant) | Fast inference, tool-calling support |
| Database | PostgreSQL + SQLAlchemy 2 | JSONB for list fields |
| Package Manager | uv | Reproducible lockfile, 10× faster than pip |

---

## The 5 LangGraph Tools

| # | Tool | What it does | Example trigger |
|---|------|-------------|-----------------|
| 1 | `log_interaction` | Parses free-text description → extracts all 14 form fields → saves to DB | *"Today I met Dr. Priya Sharma at Apollo…"* |
| 2 | `edit_interaction` | Differential update — changes only the mentioned fields, keeps everything else | *"Actually the sentiment was Neutral, not Positive"* |
| 3 | `suggest_follow_ups` | Generates 4–5 specific, HCP-tailored, time-bound follow-up actions | *"Suggest follow-ups for this visit"* |
| 4 | `check_compliance` | Audits against PhRMA Code, PDMA sample rules, Sunshine Act, off-label rules | *"Is this interaction compliant?"* |
| 5 | `recommend_materials` | Suggests clinical materials for next visit; skips what was already shared | *"What should I bring to Dr. Sharma next time?"* |

**Why these 5?**
Tools 1–2 cover the core logging workflow. Tool 3 replaces a generic "suggest followup" with HCP-specific, contextual suggestions that include the doctor's name and a timeline. Tool 4 (compliance) is unique — pharma reps face real regulatory obligations under PhRMA/PDMA, and this is the only tool in any comparable open-source implementation that addresses it. Tool 5 goes beyond "send an email" by recommending specific material types (Phase III data, MoA slides, patient case studies) tailored to what was discussed.

---

## Why LangGraph over a simple LLM chain?

The key difference is the **ReAct loop**: the LLM sees tool results and continues reasoning. This enables:

- **Multi-tool chaining**: "Check compliance and suggest follow-ups" → agent calls `check_compliance`, reads result, then calls `suggest_follow_ups`, then replies
- **Selective tool use**: if the user asks a general question, no tools are called (no wasted DB writes or LLM calls)
- **Semantic routing**: the LLM reads tool docstrings and decides which tool fits — not keyword matching

Compare this to a pipeline graph (router → tool A → tool B → tool C → END), which always runs all tools regardless of what the user asked.

---

## Project Structure

```
ai-hcp-crm/
├── .gitignore
├── README.md
├── pyproject.toml                 # uv workspace root
├── screenshots/                   # UI screenshots
│
├── backend/
│   ├── pyproject.toml             # uv project with pinned dependencies
│   ├── requirements.txt           # pip-compatible fallback
│   ├── .env.example               # environment variable template
│   ├── main.py                    # FastAPI app + lifespan startup
│   ├── database.py                # SQLAlchemy engine, SessionLocal, init_db
│   ├── models.py                  # Interaction + ChatMessage ORM models
│   ├── schemas.py                 # Pydantic request/response schemas
│   ├── agent/
│   │   ├── graph.py               # LangGraph StateGraph (ReAct loop)
│   │   └── tools.py               # 5 tools via factory pattern
│   └── routers/
│       └── interactions.py        # POST /api/chat + CRUD endpoints
│
└── frontend/
    ├── index.html                 # Vite entry point
    ├── package.json
    ├── vite.config.js             # Proxy /api → localhost:8000
    └── src/
        ├── App.jsx                # Split-screen root + handleSendMessage
        ├── App.css                # Viewport lock, flex layout
        ├── store/
        │   └── slices/
        │       ├── interactionSlice.js   # Form state (read-only, AI-only writes)
        │       └── chatSlice.js          # Messages + isLoading + sendMessage thunk
        └── components/
            ├── FormPanel/         # Left panel — all inputs readOnly
            └── ChatPanel/         # Right panel — chat UI with typing indicator
```

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Node.js | 18+ |
| PostgreSQL | 14+ |
| Groq API key | Free at [console.groq.com](https://console.groq.com) |
| uv | `pip install uv` |

---

## Setup & Run

### 1. Clone the repository

```bash
git clone https://github.com/Kanchan95/ai-hcp-crm.git
cd ai-hcp-crm
```

### 2. Create the PostgreSQL database

```bash
psql -U postgres -c "CREATE DATABASE hcp_crm;"
```

### 3. Backend

```bash
cd backend

uv venv --python 3.11
source .venv/bin/activate        # Windows: .venv\Scripts\activate
uv pip install -e "."

cp .env.example .env
# Open .env and set your GROQ_API_KEY and DATABASE_URL

uvicorn main:app --reload --port 8000
```

**Alternative (pip):**
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`

### 4. Frontend

```bash
cd ../frontend
npm install
npm run dev
```

Open `http://localhost:3000`

### Environment Variables (`backend/.env`)

```env
GROQ_API_KEY=gsk_...                           # Required — get at console.groq.com
DATABASE_URL=postgresql://postgres:password@localhost:5432/hcp_crm
AGENT_MODEL=llama-3.1-8b-instant               # Default model (fast, free tier)
# AGENT_MODEL=llama-3.3-70b-versatile          # Larger model (better quality, hits 100k/day faster)
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | Main endpoint — runs LangGraph agent, returns AI text + form_data |
| `GET` | `/api/interactions/{id}` | Fetch a specific interaction by ID |
| `DELETE` | `/api/interactions/{id}` | Delete an interaction |
| `GET` | `/api/health` | Liveness probe |

---

## Key Design Decisions

**Form is 100% read-only** — Every `<input>` and `<textarea>` has `readOnly`/`disabled`. There are no `onChange` handlers. The only write path is `dispatch(updateInteraction(form_data))` called after an API response.

**Factory pattern for tools** — `create_tools(db, state)` creates tool closures per HTTP request so they share the correct SQLAlchemy session and can write the new `interaction_id` back to the router.

**Two LLM calls per tool** — The router LLM (in agent node) only picks which tool. The extraction LLM (inside each tool) does the focused NLP work with a purpose-built prompt. This keeps each call small and accurate.

**Scroll isolation** — `html, body, #root { overflow: hidden }` locks the page. Each panel has `overflow-y: auto` on its scroll container only. Chat uses `messagesRef.scrollTop = scrollHeight` (not `scrollIntoView`) to avoid touching page scroll. FormPanel uses `useLayoutEffect` to preserve scroll position when Redux updates.

**History truncation** — Only the last 4 turns (8 messages) are sent per request, keeping token usage within the Groq free tier (100k/day).

---

## Author

**Kanchan Chowdhary**
kanchan.chowdhary95@gmail.com
Full-Stack Engineer | Bengaluru
