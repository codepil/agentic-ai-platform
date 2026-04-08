# ADR-002: Python + LangGraph + CrewAI for Agent Orchestration

**Status:** Accepted  
**Date:** 2026-04-07  
**Deciders:** Platform Architecture Team

---

## Context

The platform needs an engine that can autonomously execute an entire SDLC — requirements gathering, architecture design, code generation, QA, and deployment — driven by AI agents. The key design questions were:

1. Which **language** to use for the AI orchestration layer?
2. Which **orchestration framework** to manage multi-step, stateful workflows?
3. Which **agent framework** to coordinate multiple specialist agents per SDLC stage?

---

## Decision

Use **Python 3.12** with **LangGraph 0.2.x** for stateful SDLC workflow orchestration and **CrewAI 0.80.x** for multi-agent crew execution within each stage.

---

## Reasons

### 1. Python is the native language of the AI/LLM ecosystem

Every major AI library — LangChain, LangGraph, CrewAI, Anthropic SDK, OpenAI SDK, HuggingFace — is Python-first. Using Python eliminates translation layers, version lag, and unsupported features that Java or Node.js wrappers inevitably introduce.

### 2. LangGraph for stateful SDLC workflow

The SDLC is not a simple linear pipeline — it has loops (QA failures trigger re-runs of Dev Crew), conditional branches (requirements rejected → back to requirements crew), and durable human approval gates that can pause for hours or days.

LangGraph's `StateGraph` models this naturally:
- **Nodes** = SDLC stages (requirements, architecture, dev, QA, devops, deploy)
- **Edges** = conditional transitions based on state (approval status, QA pass/fail, iteration count)
- **`interrupt()`** = pauses the graph at approval gates and resumes via `Command(resume=...)`
- **MongoDB Atlas Checkpointer** = persists full `SDLCState` to MongoDB after every node, so runs survive server restarts, network failures, or multi-day approval delays

No other Python framework (plain Celery tasks, Prefect, Airflow) provides this combination of LLM-native state management, conditional edges, and durable human-in-the-loop interrupts.

### 3. CrewAI for multi-agent crews per stage

Each SDLC stage involves multiple specialist agents working together — a PM, BA, and SAP Analyst for requirements; a Solution Architect and ADR Writer for architecture; a Java Developer, React Developer, and Tech Lead for coding. CrewAI models this as a `Crew` with:
- **Agents** — role, goal, backstory, LLM, tools
- **Tasks** — description, context chain (output of one task feeds the next), expected output
- **Process** — `sequential` (each agent waits for the prior) or `hierarchical` (manager delegates)

LangGraph handles the *when* and *what state* to pass between stages. CrewAI handles the *how* of multi-agent collaboration within a stage. Together they cover the full orchestration problem cleanly.

### 4. Claude Sonnet + Haiku routing

The `model_router.py` routes tasks to the appropriate Claude model:
- **Claude Sonnet 4.5** — complex reasoning tasks (requirements analysis, architecture decisions, code generation)
- **Claude Haiku** — fast, cheap tasks (status summaries, simple classifications, short transforms)

The Anthropic Python SDK supports this routing natively. Implementing equivalent routing in a Java LLM wrapper would add significant boilerplate.

### 5. Mock mode for cost-free testing

Setting `MOCK_MODE=true` disables all real LLM and API calls, returning deterministic mock outputs. This allows all 84 tests to run in CI without incurring Anthropic API costs or requiring live Jira/GitHub/SAP credentials. Python's dynamic nature makes this mock injection simpler than equivalent Java approaches.

---

## Consequences

### Positive
- Full access to the Python AI/LLM ecosystem without translation wrappers
- LangGraph `interrupt()` + MongoDB checkpointer gives durable, resumable SDLC runs
- CrewAI process types (sequential/hierarchical) match each SDLC stage's collaboration model
- `MOCK_MODE=true` enables 84 tests to run in CI with zero API cost
- Independent deployment and scaling from the Java control plane

### Negative
- Two runtime languages in the platform (Python + Java)
- Python GIL limits true thread-level parallelism (mitigated by `async`/`await` + asyncio)
- LangGraph and CrewAI are relatively new frameworks — APIs may evolve

### Mitigated by
- The Java-Python boundary is a narrow, well-defined REST + SSE interface (5 endpoints)
- `MOCK_MODE` decouples framework upgrades from test stability
- LangGraph is backed by LangChain Inc. (strong enterprise support); CrewAI has rapid adoption

---

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| LangGraph alone (no CrewAI) | Single-agent per stage is less capable for complex tasks requiring specialist collaboration (PM + BA + SAP Analyst together produce better requirements than one agent alone) |
| CrewAI alone (no LangGraph) | No built-in stateful graph, conditional edges, or durable human-in-the-loop interrupt mechanism |
| Java LangChain4j | Java wrapper — lags behind Python SDK feature releases; no CrewAI equivalent; weaker LangGraph support |
| Prefect / Airflow | Data pipeline tools — not designed for LLM agent orchestration, no interrupt/resume for human gates, no native LLM state management |
| AutoGen (Microsoft) | Less structured for sequential SDLC stages; no equivalent of CrewAI's task context chaining |

---

## Related decisions

- [ADR-001](ADR-001-java-platform-core-over-python.md) — Java Spring Boot for platform control plane
- [ADR-003](ADR-003-fastapi-rest-sse-over-grpc.md) — FastAPI REST + SSE over gRPC for Java-Python bridge
