# Agent Engine

Python service that runs the autonomous SDLC workflow using **LangGraph** (stateful orchestration) and **CrewAI** (multi-agent crews). Exposes a **FastAPI REST + SSE** interface consumed by the Java `platform-app`.

---

## What it does

Given a Jira epic ID, the agent-engine runs the full software development lifecycle autonomously:

```
Intake -> Requirements Crew -> [Human Approval] -> Architecture Crew
       -> Dev Crew -> QA Crew -> [retry loop up to N times]
       -> DevOps Crew -> [Human Approval] -> Deploy to Prod
```

Each stage is a CrewAI crew (multi-agent). The orchestration is a LangGraph `StateGraph` with MongoDB Atlas checkpointing for durable state across approval gates.

---

## Project structure

```
agent-engine/
├── src/platform/
│   ├── api/
│   │   └── server.py              # FastAPI REST + SSE endpoints
│   ├── checkpointing/
│   │   └── mongo_checkpointer.py  # LangGraph MongoDB Atlas checkpointer
│   ├── config.py                  # Settings loaded from env vars
│   ├── crews/
│   │   ├── base_crew.py           # BaseCrew with mock/real mode switching
│   │   ├── requirements_crew.py   # Requirements Crew (PM + BA + SAP Analyst)
│   │   ├── architecture_crew.py   # Architecture Crew (Solution Architect + ADR Writer)
│   │   ├── dev_crew.py            # Dev Crew (Java Dev + React Dev + Tech Lead)
│   │   ├── qa_crew.py             # QA Crew (QA Engineer + Security Analyst)
│   │   ├── devops_crew.py         # DevOps Crew (DevOps Engineer + SRE)
│   │   └── output_models.py       # Pydantic output models for each crew
│   ├── graphs/
│   │   ├── sdlc_graph.py          # Builds and compiles the LangGraph StateGraph
│   │   ├── nodes/                 # One file per LangGraph node
│   │   │   ├── intake.py
│   │   │   ├── requirements.py
│   │   │   ├── requirements_approval.py  # interrupt() gate
│   │   │   ├── architecture.py
│   │   │   ├── dev.py
│   │   │   ├── qa.py
│   │   │   ├── devops.py
│   │   │   ├── staging_approval.py       # interrupt() gate
│   │   │   ├── deploy_prod.py
│   │   │   ├── qa_failed_handler.py
│   │   │   └── error_handler.py
│   │   └── edges/
│   │       └── routing.py         # Conditional edge functions
│   ├── llm/
│   │   └── model_router.py        # Routes tasks to Sonnet (complex) or Haiku (simple)
│   ├── state/
│   │   └── sdlc_state.py          # SDLCState TypedDict — single shared graph state
│   └── tools/
│       ├── crewai_tools.py        # @tool functions: Jira, GitHub, Figma
│       ├── jira_tools.py
│       ├── github_tools.py
│       └── figma_tools.py
└── tests/
    ├── conftest.py                # Fixtures, MOCK_MODE=true
    ├── test_state.py              # SDLCState shape and defaults (12 tests)
    ├── test_routing.py            # Conditional edge routing logic (16 tests)
    ├── test_nodes.py              # Individual node execution (19 tests)
    ├── test_crews.py              # Crew output models and mock execution (30 tests)
    └── test_sdlc_graph.py         # End-to-end graph compilation (7 tests)
```

---

## Setup

### Prerequisites

- Python 3.12+
- (Optional) MongoDB Atlas URI for durable state — `MemorySaver` is used in MOCK_MODE

### Install

```bash
cd agent-engine
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment variables

Create a `.env` file in `agent-engine/`:

```env
# Required for real (non-mock) mode
ANTHROPIC_API_KEY=sk-ant-...

# MongoDB Atlas (optional in MOCK_MODE)
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net
MONGO_DB_NAME=agent_platform

# Jira (optional in MOCK_MODE)
JIRA_URL=https://yourorg.atlassian.net
JIRA_USER=your@email.com
JIRA_TOKEN=your-jira-api-token

# GitHub (optional in MOCK_MODE)
GITHUB_TOKEN=ghp_...

# Figma (optional in MOCK_MODE)
FIGMA_TOKEN=figd_...

# LLM models (defaults shown)
SONNET_MODEL=claude-sonnet-4-5
HAIKU_MODEL=claude-haiku-4-5

# Set true to skip real LLM/API calls (for dev and testing)
MOCK_MODE=false
```

---

## Running

### Development (mock mode — no real API calls)

```bash
MOCK_MODE=true uvicorn src.platform.api.server:app --reload --port 8000
```

### Production

```bash
uvicorn src.platform.api.server:app --host 0.0.0.0 --port 8000 --workers 4
```

API docs available at `http://localhost:8000/docs` (Swagger UI).

---

## API reference

### Start a new SDLC run

```bash
POST /api/v1/runs
```

```bash
curl -X POST http://localhost:8000/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{
    "run_id":  "run-abc-001",
    "thread_id": "thread-abc-001",
    "jira_epic_id": "SC-42",
    "product_id": "SelfCare-001",
    "figma_url": "https://figma.com/file/abc123",
    "prd_s3_url": "s3://bucket/prd.pdf",
    "max_qa_iterations": 3
  }'
```

Returns `202 Accepted`. The graph runs in the background.

---

### Stream live agent events (SSE)

```bash
GET /api/v1/runs/{run_id}/events
```

```bash
curl -N http://localhost:8000/api/v1/runs/run-abc-001/events
```

Events emitted as each agent crew completes a stage:

```
data: {"run_id": "run-abc-001", "agent": "requirements_crew", "event_type": "state_update", "stage": "requirements", "ts": 1712345678000}
data: {"run_id": "run-abc-001", "agent": "requirements_approval", "event_type": "state_update", "stage": "requirements_approval", "ts": 1712345690000}
data: {"run_id": "run-abc-001", "event_type": "heartbeat"}
```

Final event when run finishes: `{"event_type": "run_complete"}`.

Java `platform-app` subscribes here and forwards all events to the ReactJS dashboard over WebSocket (STOMP).

---

### Poll current status

```bash
GET /api/v1/runs/{run_id}/status
```

```bash
curl http://localhost:8000/api/v1/runs/run-abc-001/status
```

```json
{
  "run_id": "run-abc-001",
  "current_stage": "requirements_approval",
  "next_nodes": ["requirements_approval"],
  "qa_iteration": 0,
  "llm_usage": {"input_tokens": 4200, "output_tokens": 1800},
  "errors": []
}
```

When `next_nodes` is non-empty, the graph is **paused at a human approval gate**.

---

### Resume after a human approval

```bash
POST /api/v1/runs/{run_id}/resume
```

```bash
# Approve — graph continues to architecture_crew
curl -X POST http://localhost:8000/api/v1/runs/run-abc-001/resume \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "approved",
    "feedback": "User stories look good, proceed",
    "approved_by": "pm-okta-user-id"
  }'

# Reject — graph loops back to requirements_crew
curl -X POST http://localhost:8000/api/v1/runs/run-abc-001/resume \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "rejected",
    "feedback": "Missing SAP inventory sync story",
    "approved_by": "pm-okta-user-id"
  }'
```

Returns `202 Accepted`. Resume events stream on the same SSE connection.

---

### Cancel a run

```bash
DELETE /api/v1/runs/{run_id}
```

```bash
curl -X DELETE http://localhost:8000/api/v1/runs/run-abc-001
```

---

## Running tests

All 84 tests run in `MOCK_MODE=true` — no real LLM or API calls required.

```bash
cd agent-engine
MOCK_MODE=true pytest tests/ -v
```

Expected output:

```
tests/test_state.py          12 passed
tests/test_routing.py        16 passed
tests/test_nodes.py          19 passed
tests/test_crews.py          30 passed
tests/test_sdlc_graph.py      7 passed
========================= 84 passed =========================
```

---

## LLM routing

Tasks are routed between two Claude models based on complexity:

| Model | Used for |
|---|---|
| `claude-sonnet-4-5` | Requirements analysis, architecture decisions, code generation |
| `claude-haiku-4-5` | Simple classification, status checks, short summaries |

Controlled by `src/platform/llm/model_router.py`. Override via `SONNET_MODEL` / `HAIKU_MODEL` env vars.

---

## How Java platform-app uses this service

```
ReactJS MFE
    |  (WebSocket STOMP)
Java platform-app (port 8080)
    |  POST /api/v1/runs              -- starts run
    |  GET  /api/v1/runs/{id}/events  -- subscribes SSE stream
    |  POST /api/v1/runs/{id}/resume  -- forwards approval decision
Agent Engine (port 8000)
    |
LangGraph StateGraph + CrewAI crews
```

The Java `AgentRunService` calls these endpoints via Spring `WebClient` and forwards SSE events to ReactJS over STOMP WebSocket. The human approval flow is driven by the Java `ApprovalController` → `ApprovalService` → this resume endpoint.

---

## Dev Crew coding standards injection

The `DevCrew` reads Java coding patterns from `platform-core` (controllers, services, repositories, DTOs) and injects them into the Java Developer agent's backstory at runtime. This ensures generated code follows the same conventions as the handwritten platform code.

See `src/platform/crews/dev_crew.py` — `_PLATFORM_CORE_SNIPPETS` class constant.
