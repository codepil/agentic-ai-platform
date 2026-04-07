# Agentic AI Platform — Blueprint

**Client:** Self-Care Products Launch (3–4 Year Strategy)
**Date:** April 2026
**Status:** Phase 0 — Architecture & Planning

---

## Overview

An agentic AI platform that autonomously handles the **entire Software Development Lifecycle (SDLC)** to build and ship self-care products. The AI agents — not humans — generate requirements, design systems, write code, run tests, and deploy services. Humans retain approval gates at critical stages.

The self-care products integrate with SAP and enterprise middleware systems. The platform itself is a 3-tier application (ReactJS + Java + MongoDB Atlas), with a Python agent engine running alongside the Java backend.

---

## Confirmed Decisions

| Concern | Decision |
|---------|----------|
| Frontend | ReactJS 18 + TypeScript, Micro-Frontends (Module Federation) |
| Backend | Java Spring Boot 3.x (orchestration APIs) |
| Database | MongoDB Atlas (M30+, multi-region) |
| Agent Orchestration | LangGraph 0.2.x (stateful SDLC workflow graph) |
| Agent Framework | CrewAI 0.80.x (multi-agent crews per SDLC stage) |
| LLM — Primary | Claude Sonnet 4.5 (complex reasoning, code generation) |
| LLM — Fast/Cheap | Claude Haiku (simple transforms, formatting, summaries) |
| Java ↔ Python Bridge | REST (FastAPI on Python, Spring WebClient on Java) + SSE for event streaming |
| Agent Memory | MongoDB Atlas Vector Search |
| Auth | Okta + OAuth2 (PKCE for MFEs, client credentials for services) |
| Agent Sandboxing | Docker-in-Docker (isolated per agent code execution task) |
| Human Gates | Async approval — Slack notification + Web UI |
| SAP Integration | SAP Integration Suite + event-driven (OData + BAPI/RFC) |
| Source Control | GitHub (multi-repo) |
| CI/CD | GitHub Actions |
| Project Management | Jira |
| Requirements Input | Jira Epics + Figma URLs + PRD documents |
| Cloud | AWS |
| Infra as Code | Terraform |
| UX Design | Figma + Style Dictionary (design tokens → ReactJS component lib) |

---

## Platform Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CONTROL PLANE (ReactJS MFE)                      │
│  Agent Dashboard | Pipeline Viewer | Approval Gates | Audit Logs    │
└────────────────────────────┬────────────────────────────────────────┘
                             │ REST / WebSocket
┌────────────────────────────▼────────────────────────────────────────┐
│                 ORCHESTRATION TIER (Java Spring Boot)               │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              LangGraph State Machine                         │   │
│  │  SDLC Workflow Graph (nodes = agent tasks, edges = state)    │   │
│  │  Requirements → Design → Code → Review → Test → Deploy       │   │
│  └───────────────────────┬──────────────────────────────────────┘   │
│                          │                                          │
│  ┌───────────────────────▼──────────────────────────────────────┐   │
│  │                   CrewAI Agent Crews                         │   │
│  │                                                              │   │
│  │  [Requirements Crew]  [Architecture Crew]  [Dev Crew]        │   │
│  │  [QA Crew]            [Security Crew]      [DevOps Crew]     │   │
│  └───────────────────────┬──────────────────────────────────────┘   │
│                          │                                          │
│  ┌───────────────────────▼──────────────────────────────────────┐   │
│  │                   Tool Layer                                 │   │
│  │  GitHub | Jira | Figma API | SAP APIs | SonarQube            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Okta OAuth2 | API Gateway | Kafka (agent task events)              │
└─────────────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                     DATA TIER (MongoDB Atlas)                       │
│                                                                     │
│  agent_runs  |  sdlc_state  |  artifacts  |  audit_trail           │
│  tool_memory |  vector_store (Atlas Search) |  approvals           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Multi-Repo Structure

```
github.com/{org}/
│
├── platform-core/                  # Java Spring Boot — orchestration APIs
├── agent-engine/                   # Python — LangGraph + CrewAI runtime
├── mfe-shell/                      # ReactJS — app shell, routing, Okta auth
├── mfe-agent-dashboard/            # ReactJS MFE — agent run viewer
├── mfe-approval-portal/            # ReactJS MFE — human review & gates
├── mfe-audit-logs/                 # ReactJS MFE — full audit trail
│
├── agent-requirements-crew/        # Python — Requirements agents
├── agent-architecture-crew/        # Python — Architecture agents
├── agent-dev-crew/                 # Python — Dev agents (React, Java, Mongo)
├── agent-qa-crew/                  # Python — QA, security, test agents
├── agent-devops-crew/              # Python — CI/CD, infra, deploy agents
│
├── sap-integration-adapter/        # Java — SAP OData/BAPI/RFC adapters
├── middleware-connectors/          # Java — Kafka, MQ, ESB connectors
│
├── shared-java-libs/               # Java — common auth, logging, MongoDB client
├── shared-python-libs/             # Python — LLM clients, tool wrappers, memory
├── shared-ui-components/           # ReactJS — Figma design system component lib
│
├── infra/                          # Terraform — AWS, MongoDB Atlas, Okta config
└── docs/                           # Architecture decisions, runbooks, ADRs
```

---

## Agent Crews & Responsibilities

### Crew 1 — Requirements Agents
| Agent | Role |
|-------|------|
| `RequirementsParser` | Reads PRDs, Jira epics, Figma links → structured user stories |
| `AcceptanceCriteriaWriter` | Generates BDD/Gherkin acceptance criteria |
| `DependencyMapper` | Maps SAP/middleware dependencies per feature |
| `ScopeGuard` | Flags ambiguity, asks clarifying questions via Jira comments |

### Crew 2 — Architecture Agents
| Agent | Role |
|-------|------|
| `SystemDesigner` | Generates architecture diagrams, ADRs |
| `SchemaDesigner` | MongoDB schema design per service |
| `APIContractWriter` | OpenAPI 3.0 spec generation |
| `SAPIntegrationPlanner` | Maps SAP BAPI/RFC/OData calls needed |

### Crew 3 — Development Agents
| Agent | Role |
|-------|------|
| `ReactComponentBuilder` | Generates ReactJS MFE components from Figma + OpenAPI specs |
| `JavaServiceBuilder` | Spring Boot microservice scaffolding + implementation |
| `MongoRepoBuilder` | MongoDB repository layer, indexes, aggregation pipelines |
| `SAPConnectorBuilder` | Generates SAP JCo/OData adapter code |
| `TestWriter` | Unit tests (JUnit 5, Jest), integration tests |

### Crew 4 — QA Agents
| Agent | Role |
|-------|------|
| `CodeReviewer` | Static analysis, code quality gates |
| `SecurityScanner` | OWASP checks, secret detection, dependency CVEs |
| `E2ETestRunner` | Playwright/Cypress test generation + execution |
| `PerformanceTester` | Load test script generation (k6/JMeter) |

### Crew 5 — DevOps Agents
| Agent | Role |
|-------|------|
| `PipelineBuilder` | Generates CI/CD pipeline configs (GitHub Actions) |
| `InfraProvisioner` | Terraform/Helm chart generation |
| `DeploymentOrchestrator` | Manages blue/green or canary deploy sequences |
| `RollbackAgent` | Monitors post-deploy, triggers rollback if SLOs breached |

---

## LangGraph SDLC Workflow

```
[INPUT: PRD / Jira Epic / Figma URL]
         │
         ▼
  ┌─────────────┐     needs clarification   ┌──────────────────────┐
  │ Requirements│ ─────────────────────────►│ Human Review Gate     │
  │    Crew     │◄──────────────────────────│ (Slack + Web UI)      │
  └──────┬──────┘         approved          └──────────────────────┘
         │
         ▼
  ┌─────────────┐
  │Architecture │──► ADRs, OpenAPI specs, MongoDB schemas → Atlas
  │    Crew     │
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │    Dev      │──► Code committed to feature branch in GitHub
  │    Crew     │
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐     fails        ┌───────────────────────────┐
  │    QA       │ ────────────────►│ Dev Crew retry             │
  │    Crew     │◄─────────────────│ (max 3 iterations)         │
  └──────┬──────┘     passes       └───────────────────────────┘
         │
         ▼
  ┌─────────────┐
  │   DevOps    │──► PR created, CI runs, deploy to staging
  │    Crew     │
  └──────┬──────┘
         │
         ▼
  [DEPLOYED TO STAGING] ──► Human sign-off ──► [PRODUCTION]
```

---

## Detailed Stack Per Tier

### Frontend (ReactJS MFEs)
```
Framework:        React 18 + TypeScript
MFE Framework:    Module Federation (Webpack 5)
State:            Zustand (lightweight, per MFE)
UI Components:    Custom lib from Figma tokens (Style Dictionary)
Auth:             Okta React SDK (@okta/okta-react)
API Client:       TanStack Query + Axios
Real-time:        WebSocket (agent run status streaming)
Testing:          Jest + React Testing Library + Playwright
Build:            Vite (dev), Webpack Module Federation (prod)
```

### Backend Orchestration (Java)
```
Framework:        Spring Boot 3.x + Spring Security
API:              REST (OpenAPI 3.0) + WebSocket (STOMP)
Auth:             Spring Security OAuth2 Resource Server (Okta)
HTTP Client:      Spring WebClient (calls Python agent engine REST API)
Messaging:        Apache Kafka (agent task events)
MongoDB:          Spring Data MongoDB + MongoDB Atlas
SAP:              SAP JCo (RFC) + Apache Olingo (OData)
Testing:          JUnit 5 + Mockito + Testcontainers
Build:            Maven + Docker + GitHub Actions
```

### Agent Engine (Python)
```
Orchestration:    LangGraph 0.2.x (stateful SDLC workflow)
Agents:           CrewAI 0.80.x (multi-agent crews)
REST Server:      FastAPI + Uvicorn (HTTP/1.1, consumed by Java backend)
Event Streaming:  Server-Sent Events (SSE) via FastAPI — Java subscribes, forwards to WebSocket
LLM Primary:      Anthropic SDK — Claude Sonnet 4.5
LLM Fast:         Anthropic SDK — Claude Haiku (simple/cheap tasks)
Memory:           MongoDB Atlas Vector Search (via PyMongo)
Tools:            GitHub API, Jira API, Figma API, custom SAP tools
Sandboxing:       Docker-in-Docker (per agent code execution)
Testing:          pytest + pytest-asyncio
Runtime:          Python 3.12 + Poetry
```

### Data (MongoDB Atlas)
```
Cluster:          Atlas M30+ (dedicated, multi-region)
Vector Search:    Atlas Vector Search (agent memory & artifact similarity)

Collections:
  agent_runs          LangGraph state snapshots, run lifecycle
  sdlc_artifacts      Generated code, specs, ADRs, pipeline configs
  audit_trail         Every agent action + reasoning chain
  approval_requests   Human gate requests, decisions, timestamps
  tool_memory         Per-agent short + long term memory
  vector_embeddings   Code chunks, docs for RAG across artifacts

Search:           Atlas Search (full-text across all artifacts)
```

---

## Java ↔ Python REST Bridge

All communication between Java (Spring Boot) and Python (FastAPI) is HTTP/1.1 REST.
Streaming agent events use Server-Sent Events (SSE) — Java subscribes and forwards to ReactJS via WebSocket.

```
Python FastAPI endpoints                  Java Spring WebClient calls
─────────────────────────────────────────────────────────────────────
POST   /api/v1/runs                   ←── start a new SDLC run
POST   /api/v1/runs/{id}/resume       ←── resume after human approval
GET    /api/v1/runs/{id}/status       ←── poll run status
GET    /api/v1/runs/{id}/events       ←── SSE stream of agent events
DELETE /api/v1/runs/{id}              ←── cancel a running run
```

**Request/Response contract (JSON):**

```json
// POST /api/v1/runs — request
{
  "run_id":       "uuid-v4",
  "thread_id":    "uuid-v4",
  "jira_epic_id": "SC-42",
  "figma_url":    "https://figma.com/file/...",
  "prd_s3_url":   null,
  "product_id":   "SelfCare-001",
  "max_qa_iterations": 3
}

// POST /api/v1/runs/{id}/resume — request
{
  "decision":    "approved",
  "feedback":    null,
  "approved_by": "okta-user-id"
}

// GET /api/v1/runs/{id}/events — SSE stream
data: {"run_id":"...","agent":"RequirementsParser","event_type":"thinking","payload":"...","ts":1712345678}
data: {"run_id":"...","agent":"RequirementsParser","event_type":"tool_call","payload":"...","ts":1712345679}
data: {"run_id":"...","agent":"","event_type":"stage_complete","payload":"requirements","ts":1712345700}
```

---

## MongoDB Atlas — Key Collection Schemas

```javascript
// agent_runs
{
  _id: ObjectId,
  run_id: "uuid-v4",
  sdlc_stage: "requirements|architecture|dev|qa|devops",
  crew_type: "requirements_crew",
  status: "running|waiting_approval|completed|failed|rolled_back",
  input: {
    jira_epic_id: "PROD-123",
    figma_url: "https://figma.com/...",
    prd_s3_url: "s3://bucket/prd.pdf"
  },
  langgraph_state: { /* full graph checkpoint JSON */ },
  iterations: 2,
  max_iterations: 3,
  artifacts: ["artifact_id_1", "artifact_id_2"],
  approval_id: "approval_uuid",
  llm_usage: { input_tokens: 12000, output_tokens: 4500, cost_usd: 0.18 },
  started_at: ISODate,
  completed_at: ISODate,
  created_by: "okta_user_id"
}

// sdlc_artifacts
{
  _id: ObjectId,
  artifact_id: "uuid",
  run_id: "uuid",
  type: "openapi_spec|java_service|react_component|test_suite|adr|pipeline_yaml",
  content: "...",
  file_path: "services/product-catalog/src/main/...",
  repo: "agent-dev-crew",
  git_commit_sha: "abc123",
  vector_embedding: [0.123, ...],
  created_at: ISODate
}
```

---

## Okta + OAuth2 Architecture

```
Users (Devs, PMs, Stakeholders)
         │
         ▼
    Okta Tenant
    ├── App: mfe-shell            (PKCE flow)
    ├── App: platform-core API    (client credentials)
    ├── App: agent-engine API     (client credentials)
    └── Groups:
        ├── platform-admin        full access
        ├── agent-operator        run agents, view all
        ├── approver              approve/reject human gates only
        └── viewer                read-only audit logs

JWT Scopes:
  agents:run       trigger agent crews
  agents:approve   approve/reject human gates
  agents:read      view runs, artifacts
  admin:manage     configure platform
```

---

## Phased Delivery Plan

### Phase 0 — Foundation (Months 1–3)
- Finalize LLM provider contract (Anthropic API, data residency)
- Set up multi-repo GitHub org, branch protection rules
- Provision Okta tenant, app registrations, groups
- MongoDB Atlas cluster + VPC peering to AWS
- SAP sandbox environment + Integration Suite configured
- Figma design system tokens → Style Dictionary → shared-ui-components
- Terraform state in S3, base AWS account structure
- ADR-001: Document all architecture decisions

### Phase 1 — Core Platform (Months 4–9)
- LangGraph workflow engine (Python) + FastAPI REST bridge to Java
- Requirements Crew + Architecture Crew operational
- MongoDB Atlas agent state/memory schema live
- Human approval gate — Slack notification + Web UI
- Audit trail: every agent action logged with reasoning
- mfe-agent-dashboard + mfe-approval-portal live

### Phase 2 — Dev & QA Crews (Months 10–18)
- Dev Crew generating ReactJS + Java code from OpenAPI specs + Figma
- QA Crew with automated test generation and execution
- SAP Integration Planner generating OData/BAPI adapter code
- Feedback loop: QA fails → Dev Crew retries (LangGraph cycles, max 3)
- Security scanning integrated into QA Crew
- Full GitHub Actions pipeline generation by DevOps Crew

### Phase 3 — DevOps Crew + SAP Full Integration (Year 2–3)
- Full CI/CD pipeline generation per service
- SAP bidirectional sync agents (order, inventory, product master)
- Self-healing: RollbackAgent monitors staging/prod SLOs
- Multiple parallel SDLC runs (concurrent LangGraph instances)
- Infra provisioning via Terraform generation agents

### Phase 4 — Scale & Optimize (Year 3–4)
- Agent performance analytics dashboard
- LLM cost optimization: route by task complexity (Sonnet vs Haiku)
- Cross-product learning: agents learn from prior SDLC runs via vector memory
- Full self-care product portfolio managed autonomously
- Agent-generated documentation and runbooks

---

## Phase 0 Sprint Plan (Months 1–3)

### Sprint 1–2: Infrastructure Foundation
- [ ] AWS account structure (dev / staging / prod)
- [ ] MongoDB Atlas cluster + VPC peering to AWS
- [ ] Okta tenant setup, app registrations, groups
- [ ] GitHub org, repos created, branch protection rules
- [ ] Terraform state in S3 + DynamoDB lock

### Sprint 3–4: SAP Sandbox + Integration
- [ ] SAP sandbox environment provisioned
- [ ] SAP Integration Suite configured
- [ ] Inventory OData endpoints mapped
- [ ] Product/Order BAPI catalog documented
- [ ] sap-integration-adapter skeleton + first OData call working

### Sprint 5–6: Platform Core Skeleton
- [ ] Spring Boot app with Okta JWT validation
- [ ] MongoDB Atlas connection + base collections
- [ ] FastAPI REST server skeleton in agent-engine (POST /runs, POST /runs/{id}/resume, GET /runs/{id}/events SSE)
- [ ] Kafka cluster + first topic (agent.events)
- [ ] GitHub Actions pipeline for platform-core

### Sprint 7–8: MFE Shell + Design System
- [ ] Figma design tokens exported → Style Dictionary → shared-ui-components
- [ ] mfe-shell with Okta login, Module Federation config
- [ ] mfe-agent-dashboard skeleton (WebSocket connected)
- [ ] CI/CD for all ReactJS repos

### Sprint 9–10: First Agent Run (Requirements Crew)
- [ ] LangGraph graph for requirements stage
- [ ] CrewAI Requirements Crew: 4 agents operational
- [ ] Jira integration: read epic, write sub-tasks
- [ ] Figma API: read design metadata
- [ ] MongoDB agent_run state persistence
- [ ] Human approval gate: Slack + web UI
- [ ] End-to-end: Jira Epic → Requirements Crew → output → approval

### Sprint 11–12: Audit + Observability
- [ ] Full audit trail to MongoDB (every agent action + reasoning)
- [ ] mfe-audit-logs MFE live
- [ ] LLM token cost tracking per run
- [ ] Alert: agent stuck > 30 min → Slack escalation
- [ ] Load test FastAPI REST bridge (k6 against /events SSE endpoint)

---

## Team Structure

### Year 1 Core Team
| Role | Count | Focus |
|------|-------|-------|
| Platform Architect / Tech Lead | 1 | Overall architecture, decisions, cross-team alignment |
| Java Engineers | 2 | Spring Boot, WebClient REST bridge, SAP adapters |
| Python AI Engineers | 2 | LangGraph, CrewAI, prompt engineering |
| ReactJS Engineers | 2 | MFE shell, dashboards, design system |
| MongoDB / Data Engineer | 1 | Atlas schema, vector search, aggregations |
| DevOps / Infra Engineer | 1 | AWS, Terraform, GitHub Actions |
| SAP Integration Specialist | 1 | OData, BAPI, SAP Integration Suite |

### Phase 2+ Additions
| Role | Count | Trigger |
|------|-------|---------|
| Python AI Engineer | +1 | Dev + QA crews scaling |
| QA Automation Engineer | +1 | Validating agent-generated tests |
| Security Engineer | +1 | Agent sandboxing, OWASP, secrets mgmt |

---

## Cost Model

| Item | Est. Monthly (Year 1) |
|------|-----------------------|
| Claude Sonnet 4.5 (complex tasks) | $800–2,000 |
| Claude Haiku (simple/fast tasks) | $100–300 |
| MongoDB Atlas M30 | $500–800 |
| AWS (EKS, MSK Kafka, ALB, etc.) | $1,500–3,000 |
| Okta (per user licensing) | $200–500 |
| GitHub Teams | $100–200 |
| **Total** | **~$3,200–6,800/mo** |

> Route all simple agent tasks (formatting, summarising, simple transforms) to Claude Haiku — this alone can cut LLM costs by 60–70%.

---

## Key Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| LLM hallucinations in generated code | Mandatory QA Crew + static analysis gates before any commit |
| SAP integration complexity | Stand up SAP sandbox in Month 1 — agents need real API contracts early |
| Agent infinite loops | LangGraph max retry limits (3) + human escalation on breach |
| Okta + multi-repo permissions | Agents use scoped tokens per repo/service, never admin credentials |
| LLM cost runaway | Token usage tracked per run from Day 1, budget alerts in AWS |
| Agent sandboxing escape | Docker-in-Docker with no network egress except approved tool endpoints |

---

## Immediate Next Steps (This Week)

1. Lock Anthropic API contract — usage limits, data residency confirmation
2. Create GitHub org — define repo naming conventions and branch policies
3. Provision Okta tenant — everything downstream blocks on auth
4. Request SAP sandbox access — longest lead time item, start immediately
5. Spin up MongoDB Atlas dev cluster — free tier acceptable to start
6. Write ADR-001 — document all decisions in this blueprint as the team's canonical reference

---

## Next Deep-Dive Sections

- [ ] LangGraph SDLC workflow — detailed node/edge definitions, state schema, checkpointing
- [ ] CrewAI crew definitions — agent roles, prompts, tool bindings per crew
- [ ] Java Spring Boot project structure — module layout, WebClient REST bridge to agent engine
- [ ] MongoDB Atlas schema — full collection design, indexes, vector search config
- [ ] Figma → ReactJS pipeline — design token export, Style Dictionary config, MFE architecture
- [ ] SAP integration patterns — OData vs BAPI decision matrix, event-driven sync design
