# ADR-004: 3-Tier Architecture with Platform-Core as Context Enrichment Gateway

**Status:** Accepted  
**Date:** 2026-04-07  
**Deciders:** Platform Architecture Team

---

## Context

The client's strategy is to launch multiple self-care products over 3-4 years, each integrating with SAP and enterprise middleware. The AI agents need rich, accurate context to make high-quality decisions — generic LLM prompts without domain context produce generic outputs.

Two architectural questions needed answering:

1. Should the platform follow a traditional **3-tier architecture** (presentation, application, data) or adopt a flat/serverless model?
2. Where and how should **enterprise system data** (Jira epics, SAP product catalogs, Figma designs, existing codebases) be gathered and injected into agent prompts?

---

## Decision

Adopt a **3-tier architecture** with an additional internal service tier for the agent engine:

```
Tier 1 — Presentation:    ReactJS MFEs (Module Federation)
Tier 2 — Application:     Java platform-core (Spring Boot) + Python agent-engine (FastAPI)
Tier 3 — Data:            MongoDB Atlas (state, artifacts, audit, vector search)
```

Within Tier 2, **Java platform-core acts as a Context Enrichment Gateway** — it fetches data from enterprise systems (Jira, SAP, Figma, GitHub, MongoDB history) and forwards enriched context to the agent-engine when starting or resuming SDLC runs.

---

## Why 3-tier

### 1. Proven pattern for enterprise systems at scale

The client already operates enterprise Java services in a 3-tier model. The platform adopting the same pattern means:
- Existing infrastructure, deployment pipelines, and monitoring practices apply directly
- Security boundaries (network policies, API gateways, Okta scopes) are well understood in this model
- New platform engineers do not need to learn an unfamiliar architectural style

### 2. Clear separation of concerns

Each tier has a single, well-defined responsibility:

| Tier | Responsibility | Technology |
|---|---|---|
| Presentation | User interaction, approval workflows, run monitoring | ReactJS 18, Module Federation MFEs |
| Application | Business logic, AI orchestration, security enforcement | Java Spring Boot + Python FastAPI |
| Data | Persistent state, vector memory, audit trail | MongoDB Atlas |

This separation makes each tier independently testable, scalable, and replaceable.

### 3. Independent scaling profiles

- **Presentation tier** — stateless CDN-served MFEs, scales via CloudFront
- **Application tier** — Java pod (I/O bound: REST, WebSocket, SSE) scales differently from Python pod (CPU/memory bound: LLM calls, CrewAI) — two separate ECS services with separate autoscaling policies
- **Data tier** — MongoDB Atlas M30+ with horizontal sharding, independent of application load

A flat serverless model would couple these scaling dimensions together.

### 4. Security boundary enforcement

Okta JWT authentication and scope enforcement happen entirely in the Java application tier. The ReactJS frontend never holds long-lived credentials. The agent-engine has no public-facing ports — it is only reachable from `platform-app` inside the VPC. MongoDB Atlas is accessible only from within the VPC via Private Link.

This model maps cleanly to AWS VPC security groups: public subnet (ALB), private subnet (Java + Python services), isolated subnet (MongoDB Atlas Private Link endpoint).

---

## Platform-core as Context Enrichment Gateway

### The problem: agents need domain context

An AI agent asked to "generate user stories for epic SC-42" with no additional context will produce generic output. To generate accurate, actionable user stories for a self-care product that integrates with SAP, the agent needs:

- The full Jira epic description, acceptance criteria, linked sub-tasks
- SAP product catalog entries and inventory data for the relevant product line
- Figma design specifications and component inventory
- Existing API contracts from GitHub (OpenAPI specs, service interfaces)
- Historical run data — what similar epics produced in prior runs (vector search)

This context cannot live in the agent-engine — the agent-engine has no Okta token, no SAP JCo connection, no Jira credentials, and should not. Its job is LLM orchestration, not enterprise integration.

### The solution: platform-core fetches and forwards enriched context

When a user triggers a new SDLC run, `platform-app` does the following **before** calling `POST /api/v1/runs` on the agent-engine:

```
User triggers run (POST /api/v1/runs via ReactJS)
        |
        v
Java AgentRunService
        |
        |-- 1. Fetch Jira epic + linked sub-tasks (JiraClient)
        |-- 2. Fetch SAP product catalog + inventory snapshot (SapODataClient)
        |-- 3. Fetch Figma file + component list (FigmaClient)
        |-- 4. Fetch existing OpenAPI specs from GitHub (GitHubClient)
        |-- 5. Query MongoDB vector search for similar past runs
        |
        v
Assemble EnrichedRunContext { epic, sapSnapshot, figmaSpec, existingApis, similarRuns }
        |
        v
POST /api/v1/runs to agent-engine with enriched context payload
        |
        v
Agent-engine injects context into crew backstories + task descriptions
        |
        v
LangGraph SDLC workflow runs with full domain context
```

### Why this is a key architectural advantage

**1. Agents produce domain-specific, not generic, output**

The Requirements Crew receives the actual SAP inventory model, the Figma component list, and similar past epics — not just a Jira ID. This directly improves the quality of generated user stories, architecture decisions, and code.

**2. Credentials and security stay in Java**

The agent-engine never holds Okta tokens, SAP JCo passwords, Jira API tokens, or GitHub PATs. All enterprise system credentials are managed in `platform-app` via Spring Boot secrets (AWS Secrets Manager). The agent-engine receives pre-fetched, sanitised context over its internal REST interface.

**3. Context can be progressively enriched at each approval gate**

When a run is resumed after a requirements approval, `platform-app` can re-fetch updated context before resuming:
- Jira sub-tasks created during the requirements phase
- Any SAP data changes since the run started
- Architect's comments added to the Figma file

This makes each SDLC stage smarter than the last, not stuck with stale context from run start.

**4. Platform-core becomes an enterprise context aggregator over time**

As the platform matures, platform-core's context enrichment layer can be extended without touching the agent-engine:

| Enhancement | What platform-core fetches | Benefit to agents |
|---|---|---|
| Phase 1 (now) | Jira epic, SAP catalog, Figma specs | Basic domain context |
| Phase 2 | GitHub repo history, existing test suites, SonarQube metrics | Dev and QA crews avoid duplicating existing code |
| Phase 3 | Production incident history (PagerDuty), SLA metrics | DevOps crew generates more resilient deployment configs |
| Phase 4 | Customer feedback (Salesforce), NPS data | Requirements crew prioritises user-impacting stories |
| Phase 5 | Vector search over all past SDLC runs | Crews learn from previous platform output |

Each phase adds richer context without modifying a single line of LangGraph or CrewAI code.

**5. Reduces token consumption and LLM cost**

Platform-core can pre-filter context before injection — only the relevant SAP products, only the Figma components used in this product line, only the top 3 similar past runs. Sending 200 tokens of focused context rather than 2000 tokens of raw data directly reduces Anthropic API cost on every run.

---

## Architecture diagram

```
                        ┌─────────────────────────────┐
                        │  ReactJS MFEs (Tier 1)       │
                        │  Dashboard | Approvals | Logs │
                        └──────────────┬──────────────┘
                                       │ REST / WebSocket (STOMP)
                        ┌──────────────▼──────────────┐
                        │  Java platform-core (Tier 2) │
                        │                             │
         ┌──────────────┤  Context Enrichment Gateway ├──────────────┐
         │              │                             │              │
         v              └──────────────┬──────────────┘              v
   ┌──────────┐                        │ REST + SSE           ┌──────────────┐
   │   Jira   │         ┌──────────────▼──────────────┐       │     SAP      │
   │  GitHub  │         │  Python agent-engine (Tier 2)│       │  (JCo/OData) │
   │  Figma   │         │  LangGraph + CrewAI          │       └──────────────┘
   └──────────┘         │  (receives enriched context) │
                        └──────────────┬──────────────┘
                                       │
                        ┌──────────────▼──────────────┐
                        │  MongoDB Atlas (Tier 3)       │
                        │  State | Artifacts | Vectors  │
                        └─────────────────────────────┘
```

---

## Consequences

### Positive
- Proven enterprise architecture pattern — familiar to client's existing Java teams
- Clear security boundary: enterprise credentials never leave Java tier
- Context enrichment layer improves agent output quality at every stage
- Each tier scales independently (CDN, ECS autoscaling, Atlas horizontal sharding)
- Progressive enhancement path: richer context in future phases without changing agent code

### Negative
- More moving parts than a flat serverless architecture
- Context enrichment adds latency at run start (parallel fetching from Jira, SAP, Figma)
- Requires Java engineers to maintain enterprise integration adapters in platform-core

### Mitigated by
- Context fetching is parallelised (CompletableFuture / WebClient reactive calls) — latency impact is the slowest single source, not the sum
- `lib-sap`, Jira client, Figma client are shared libraries — written once, used across all platform services
- Enriched context quality improvement outweighs the startup latency cost

---

## Related decisions

- [ADR-001](ADR-001-java-platform-core-over-python.md) — Java Spring Boot for platform control plane
- [ADR-002](ADR-002-python-langgraph-crewai-for-agent-orchestration.md) — Python + LangGraph + CrewAI for agent orchestration
- [ADR-003](ADR-003-fastapi-rest-sse-over-grpc.md) — FastAPI REST + SSE over gRPC for Java-Python bridge
