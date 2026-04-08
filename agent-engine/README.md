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

### Full round-trip sequence

```
User (ReactJS MFE)
  |
  | POST /api/v1/runs  (HTTP, Okta JWT)
  v
Java platform-app  [AgentRunService]
  |
  | 1. Persist AgentRun to MongoDB (status=running)
  | 2. POST /api/v1/runs  -->  Agent Engine
  |                              |
  |                              | 202 Accepted
  |                              |
  | 3. GET /api/v1/runs/{id}/events  (SSE, long-lived)
  |    <-- data: {"agent":"requirements_crew", "event_type":"state_update", ...}
  |    <-- data: {"event_type":"approval_requested", ...}
  |    <-- data: {"agent":"architecture_crew", "event_type":"state_update", ...}
  |    <-- data: {"event_type":"run_complete"}
  |
  | 4. Each SSE event is:
  |      a. Broadcast to ReactJS via WebSocket STOMP (/topic/runs/{id})
  |      b. Written to MongoDB audit trail (async, non-blocking)
  |      c. Parsed for special types (approval_requested, run_complete, error)
  |
  | 5. On approval_requested:
  |      - MongoDB ApprovalRequest document created
  |      - Slack notification sent to #platform-oncall
  |
User (ReactJS Approval Portal MFE)
  |
  | POST /api/v1/approvals/{id}/decide  (HTTP, Okta JWT, scope: agents:approve)
  v
Java platform-app  [ApprovalService]
  |
  | POST /api/v1/runs/{id}/resume  -->  Agent Engine
  |                                       |
  |                                       | LangGraph Command(resume=...) unblocks graph
  |                                       |
  | 6. Re-subscribes to SSE stream  <-----+
  |    <-- data: {"agent":"architecture_crew", ...}
  |    ...continues until run_complete
  v
ReactJS dashboard updated in real time via WebSocket
```

### Event types emitted by the SSE stream

| `event_type` | When emitted | Java action |
|---|---|---|
| `state_update` | After each LangGraph node completes | Broadcast to WebSocket, write audit |
| `approval_requested` | Graph paused at `interrupt()` gate | Create `ApprovalRequest` in MongoDB, Slack alert |
| `stage_complete` | End of each SDLC stage | Update `current_stage` in MongoDB |
| `run_complete` | Graph finished all nodes | Update status to `completed` in MongoDB |
| `error` | Agent crew or tool call failed | Append to `errors[]` in MongoDB, Slack alert |
| `heartbeat` | Every 300s of inactivity | No action — keeps connection alive |

### Error handling

**Agent-engine unreachable at run start**
- Java `AgentRunService` catches the WebClient error
- Run status set to `failed` in MongoDB
- Slack oncall alert fired
- ReactJS receives `failed` status on next poll

**SSE stream disconnects mid-run** (network blip, agent-engine restart)
- `handleSseError()` fires in `AgentRunService`
- Run status set to `failed` in MongoDB
- Error appended to `errors[]` array
- Slack oncall alert fired
- No automatic reconnection in the current implementation — oncall must investigate and manually re-trigger the run if appropriate

**Agent-engine returns an `error` event** (crew failure, LLM timeout)
- Error message appended to `errors[]` in MongoDB
- Run continues if the LangGraph error handler node handles it; otherwise the graph terminates with `run_complete` carrying the error state

**Approval resume fails** (agent-engine down when approver submits decision)
- `ApprovalService` catches the WebClient error
- Approval decision is persisted in MongoDB
- Slack alert sent — oncall can retry the resume once agent-engine recovers

### Local development

Run both services simultaneously:

```bash
# Terminal 1 — agent-engine
cd agent-engine
MOCK_MODE=true uvicorn src.platform.api.server:app --reload --port 8000

# Terminal 2 — platform-app
cd platform-core
OKTA_ISSUER_URI=https://placeholder.okta.example.com/oauth2/default \
MONGO_URI=mongodb://localhost:27017/agent_platform \
AGENT_ENGINE_BASE_URL=http://localhost:8000 \
mvn spring-boot:run -pl platform-app
```

The Java app connects to the agent-engine at `http://localhost:8000` via `AGENT_ENGINE_BASE_URL`.

---

## Dev Crew coding standards injection

The `DevCrew` reads Java coding patterns from `platform-core` (controllers, services, repositories, DTOs) and injects them into the Java Developer agent's backstory at runtime. This ensures generated code follows the same conventions as the handwritten platform code.

See `src/platform/crews/dev_crew.py` — `_PLATFORM_CORE_SNIPPETS` class constant.
