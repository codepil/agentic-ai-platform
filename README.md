# Agentic AI Platform — Documentation Index

Start here. Every deep-dive session produces a file in the relevant folder below.

## Master Blueprint
- [blueprint.md](blueprint.md) — Full platform overview, all decisions, phased delivery plan

---

## Deep-Dive Sessions

### 01 — Architecture
| File | Status | Description |
|------|--------|-------------|
| [decisions/ADR-001](01-architecture/decisions/ADR-001-java-platform-core-over-python.md) | Done | Java Spring Boot for platform control plane over Python |
| [decisions/ADR-002](01-architecture/decisions/ADR-002-python-langgraph-crewai-for-agent-orchestration.md) | Done | Python + LangGraph + CrewAI for agent orchestration |
| [decisions/ADR-003](01-architecture/decisions/ADR-003-fastapi-rest-sse-over-grpc.md) | Done | FastAPI REST + SSE over gRPC for Java-Python bridge |
| [decisions/ADR-004](01-architecture/decisions/ADR-004-three-tier-architecture-with-context-enrichment.md) | Done | 3-tier architecture with platform-core context enrichment gateway |
| [diagrams/01-platform-overview.md](01-architecture/diagrams/01-platform-overview.md) | Done | Full 3-tier platform overview (presentation → application → data) |
| [diagrams/02-sdlc-workflow.md](01-architecture/diagrams/02-sdlc-workflow.md) | Done | LangGraph SDLC state machine with interrupt gates, crews, checkpoints |
| [diagrams/03-aws-infrastructure.md](01-architecture/diagrams/03-aws-infrastructure.md) | Done | VPC topology, ECS, ALB, Atlas PrivateLink — AWS infrastructure view |
| [diagrams/04-data-flow.md](01-architecture/diagrams/04-data-flow.md) | Done | Sequence diagram: start run + approval resume flows |

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
| [prompts/](02-agent-engine/crewai/) | N/A | Prompts (role, goal, backstory, task descriptions) documented inline in crewai/*.md — no separate template files needed until a dedicated prompt engineer iterates independently of code |

### 03 — Platform Core (Java)
| File | Status | Description |
|------|--------|-------------|
| [project-structure.md](03-platform-core/project-structure.md) | Done | Spring Boot module layout, coding standards, shared libs |
| [agent-engine/README.md](agent-engine/README.md) | Done | Java ↔ Python REST bridge — sequence diagram, SSE events, error handling (in agent-engine README) |
| [sap-integration.md](03-platform-core/sap-integration.md) | Pending | SAP adapter patterns |

### 04 — Frontend (ReactJS MFEs)
| File | Status | Description |
|------|--------|-------------|
| [mfe-architecture.md](04-frontend/mfe-architecture.md) | Pending | Module Federation setup, MFE communication |
| [design-system.md](04-frontend/design-system.md) | Pending | Figma tokens → Style Dictionary → component lib |

### 05 — Data (MongoDB Atlas)
| File | Status | Description |
|------|--------|-------------|
| [schema-design.md](05-data/schema-design.md) | Done | Full collection design, indexes, retention, Atlas sizing |
| [vector-search.md](05-data/vector-search.md) | Done | Atlas Vector Search config, query patterns, context enrichment integration |
| [init-mongo.js](05-data/init-mongo.js) | Done | mongosh init script — collections, validators, indexes, TTLs, seed data |
| [vector-search-index.json](05-data/vector-search-index.json) | Done | Atlas Vector Search index definition (Atlas CLI input) |

### 06 — Infrastructure
| File | Status | Description |
|------|--------|-------------|
| [aws-architecture.md](06-infrastructure/aws-architecture.md) | Done | VPC topology, ECS Fargate, ALB, Atlas PrivateLink, IAM, cost estimate |
| [terraform/README.md](06-infrastructure/terraform/README.md) | Done | Deploy guide: S3 backend, secrets bootstrap, ECR push, Atlas setup |
| [terraform/modules/vpc/](06-infrastructure/terraform/modules/vpc/) | Done | VPC, subnets (public/private/isolated), NAT GWs, Flow Logs |
| [terraform/modules/alb/](06-infrastructure/terraform/modules/alb/) | Done | Internet-facing ALB, HTTPS, WebSocket listener rule |
| [terraform/modules/ecs/](06-infrastructure/terraform/modules/ecs/) | Done | ECS Fargate cluster, platform-app + agent-engine services, autoscaling |
| [terraform/modules/ecr/](06-infrastructure/terraform/modules/ecr/) | Done | ECR repos, KMS encryption, lifecycle policies, IAM repo policies |
| [terraform/modules/secrets/](06-infrastructure/terraform/modules/secrets/) | Done | Secrets Manager secrets (7 secrets, KMS, placeholder bootstrap) |
| [terraform/modules/mongodb/](06-infrastructure/terraform/modules/mongodb/) | Done | MongoDB Atlas cluster, PrivateLink, database user, IP allowlist |
| [terraform/modules/monitoring/](06-infrastructure/terraform/modules/monitoring/) | Done | CloudWatch dashboard, 9 alarms, SNS, log metric filters |
| [terraform/environments/dev/](06-infrastructure/terraform/environments/dev/) | Done | Dev environment wiring (M10, 1 AZ, MOCK_MODE=true) |
| [terraform/environments/prod/](06-infrastructure/terraform/environments/prod/) | Done | Prod environment wiring (M30, 2 AZs, HA, deletion protection) |

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
