# Agentic AI Platform — Documentation Index

Start here. Every deep-dive session produces a file in the relevant folder below.

## Master Blueprint
- [blueprint.md](blueprint.md) — Full platform overview, all decisions, phased delivery plan

---

## Deep-Dive Sessions

### 01 — Architecture
| File | Status | Description |
|------|--------|-------------|
| [decisions/](01-architecture/decisions/) | — | Architecture Decision Records (ADRs) |
| [diagrams/](01-architecture/diagrams/) | — | System diagrams |

### 02 — Agent Engine
| File | Status | Description |
|------|--------|-------------|
| [langgraph/workflow.md](02-agent-engine/langgraph/workflow.md) | Done | LangGraph SDLC workflow — nodes, edges, state, checkpointing |
| [langgraph/state-schema.md](02-agent-engine/langgraph/state-schema.md) | Pending | Full TypedDict state definitions |
| [crewai/requirements-crew.md](02-agent-engine/crewai/requirements-crew.md) | Done | Requirements Crew — agents, prompts, tools |
| [crewai/architecture-crew.md](02-agent-engine/crewai/architecture-crew.md) | Done | Architecture Crew |
| [crewai/dev-crew.md](02-agent-engine/crewai/dev-crew.md) | Done | Dev Crew |
| [crewai/qa-crew.md](02-agent-engine/crewai/qa-crew.md) | Done | QA Crew |
| [crewai/devops-crew.md](02-agent-engine/crewai/devops-crew.md) | Done | DevOps Crew |
| [prompts/](02-agent-engine/prompts/) | Pending | Prompt templates per agent |

### 03 — Platform Core (Java)
| File | Status | Description |
|------|--------|-------------|
| [project-structure.md](03-platform-core/project-structure.md) | Pending | Spring Boot module layout |
| [rest-bridge.md](03-platform-core/rest-bridge.md) | Pending | Java ↔ Python REST bridge (FastAPI + Spring WebClient + SSE) |
| [sap-integration.md](03-platform-core/sap-integration.md) | Pending | SAP adapter patterns |

### 04 — Frontend (ReactJS MFEs)
| File | Status | Description |
|------|--------|-------------|
| [mfe-architecture.md](04-frontend/mfe-architecture.md) | Pending | Module Federation setup, MFE communication |
| [design-system.md](04-frontend/design-system.md) | Pending | Figma tokens → Style Dictionary → component lib |

### 05 — Data (MongoDB Atlas)
| File | Status | Description |
|------|--------|-------------|
| [schema-design.md](05-data/schema-design.md) | Pending | Full collection design, indexes |
| [vector-search.md](05-data/vector-search.md) | Pending | Atlas Vector Search config for agent memory |

### 06 — Infrastructure
| File | Status | Description |
|------|--------|-------------|
| [aws-architecture.md](06-infrastructure/aws-architecture.md) | Pending | AWS account structure, EKS, networking |
| [terraform-structure.md](06-infrastructure/terraform-structure.md) | Pending | Terraform module layout |
| [cicd-pipeline.md](06-infrastructure/cicd-pipeline.md) | Pending | GitHub Actions workflow design |

### 07 — Security
| File | Status | Description |
|------|--------|-------------|
| [okta-oauth2.md](07-security/okta-oauth2.md) | Pending | Okta tenant setup, scopes, token flows |
| [agent-sandboxing.md](07-security/agent-sandboxing.md) | Pending | Docker-in-Docker, network egress controls |

### 08 — Integration
| File | Status | Description |
|------|--------|-------------|
| [sap-patterns.md](08-integration/sap-patterns.md) | Pending | OData vs BAPI decision matrix, event-driven sync |
| [kafka-design.md](08-integration/kafka-design.md) | Pending | Topic design, consumer groups, agent events |
