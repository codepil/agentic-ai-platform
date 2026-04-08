# Platform Overview — Agentic AI SDLC Platform

This diagram provides a full 3-tier view of the Agentic AI SDLC Platform. The **Presentation tier** delivers four React micro-frontends via CloudFront and S3. The **Application tier** is split into two services: `platform-core` (Spring Boot, Java) handles orchestration, approvals, and real-time WebSocket streaming, while `agent-engine` (FastAPI, Python) runs the LangGraph state machine and five CrewAI agent crews. The **Data tier** is a single MongoDB Atlas M30 cluster whose collections cover run state, approvals, audit trails, SDLC artifacts, and LangGraph checkpoints. External integrations — Okta, Jira, GitHub, Figma, SAP, Slack, and Anthropic — are shown on the right with labeled connections to the service that owns each integration.

```mermaid
flowchart TD

    %% ─────────────────────────────────────────
    %% TIER 1 — PRESENTATION
    %% ─────────────────────────────────────────
    subgraph T1["TIER 1 — Presentation (CloudFront + S3 / React MFEs)"]
        direction TB
        CF["CloudFront + S3\n(ReactJS MFE Host Shell)"]
        MFE1["mfe-agent-dashboard"]
        MFE2["mfe-approval-portal"]
        MFE3["mfe-audit-logs"]
        MFE4["mfe-pipeline-viewer"]
        CF --> MFE1 & MFE2 & MFE3 & MFE4
    end

    DNS["Route 53\n(DNS)"]
    ALB_PUB["ALB\n(internet-facing)"]

    DNS -->|"HTTPS"| ALB_PUB
    MFE1 & MFE2 & MFE3 & MFE4 -->|"REST / WebSocket"| ALB_PUB

    %% ─────────────────────────────────────────
    %% TIER 2 — APPLICATION
    %% ─────────────────────────────────────────
    subgraph T2["TIER 2 — Application"]
        direction LR

        subgraph CORE["platform-core  |  ECS Fargate  |  :8080  (Spring Boot / Java)"]
            direction TB
            RC["RunController"]
            AC["ApprovalController"]
            ARS["AgentRunService"]
            AS["ApprovalService"]
            AEB["AgentEventBroadcaster\n(WebSocket STOMP)"]
            RC --> ARS
            AC --> AS
            ARS --> AEB
        end

        subgraph ENGINE["agent-engine  |  ECS Fargate  |  :8000  (FastAPI / Python)  — internal only"]
            direction TB
            LG["LangGraph StateGraph\n(stateful workflow)"]
            CR1["Requirements Crew"]
            CR2["Architecture Crew"]
            CR3["Dev Crew"]
            CR4["QA Crew"]
            CR5["DevOps Crew"]
            LLM["Claude Sonnet + Haiku\n(via Anthropic API)"]
            LG --> CR1 & CR2 & CR3 & CR4 & CR5
            CR1 & CR2 & CR3 & CR4 & CR5 --> LLM
        end
    end

    ALB_PUB -->|"HTTP :8080"| CORE
    CORE -->|"HTTP :8000 (internal VPC)"| ENGINE

    %% ─────────────────────────────────────────
    %% EXTERNAL SYSTEMS
    %% ─────────────────────────────────────────
    subgraph EXT["External Systems"]
        direction TB
        OKTA["Okta\n(OAuth2 / JWT)"]
        JIRA["Jira\n(epics, sub-tasks)"]
        GH["GitHub\n(repos, PRs)"]
        FIGMA["Figma\n(design specs)"]
        SAP["SAP\n(OData / BAPI)"]
        SLACK["Slack\n(notifications)"]
        ANTHRO["Anthropic API\n(Claude)"]
    end

    CORE -->|"validate tokens"| OKTA
    CORE -->|"Slack alerts"| SLACK
    ENGINE -->|"create epics & sub-tasks"| JIRA
    ENGINE -->|"push code & PRs"| GH
    ENGINE -->|"read design specs"| FIGMA
    ENGINE -->|"OData / BAPI calls"| SAP
    ENGINE -->|"LLM inference"| ANTHRO

    %% ─────────────────────────────────────────
    %% TIER 3 — DATA
    %% ─────────────────────────────────────────
    subgraph T3["TIER 3 — Data  (MongoDB Atlas M30)"]
        direction LR
        COL1[("agent_runs")]
        COL2[("approval_requests")]
        COL3[("audit_trail")]
        COL4[("sdlc_artifacts")]
        COL5[("context_snapshots")]
        COL6[("vector_embeddings")]
        COL7[("langgraph_checkpoints")]
    end

    CORE -->|"read / write run state"| COL1
    CORE -->|"read / write approvals"| COL2
    CORE -->|"append events"| COL3
    ENGINE -->|"write artifacts"| COL4
    ENGINE -->|"read / write context"| COL5
    ENGINE -->|"RAG lookups"| COL6
    ENGINE -->|"persist graph state"| COL7

    %% ─────────────────────────────────────────
    %% STYLES
    %% ─────────────────────────────────────────
    classDef mfe fill:#dbeafe,stroke:#2563eb,color:#1e3a5f
    classDef svc fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef crew fill:#fef9c3,stroke:#ca8a04,color:#713f12
    classDef ext fill:#f3e8ff,stroke:#7c3aed,color:#3b0764
    classDef db fill:#ffe4e6,stroke:#e11d48,color:#881337
    classDef infra fill:#f1f5f9,stroke:#64748b,color:#1e293b

    class MFE1,MFE2,MFE3,MFE4 mfe
    class RC,AC,ARS,AS,AEB svc
    class CR1,CR2,CR3,CR4,CR5,LG,LLM crew
    class OKTA,JIRA,GH,FIGMA,SAP,SLACK,ANTHRO ext
    class COL1,COL2,COL3,COL4,COL5,COL6,COL7 db
    class CF,DNS,ALB_PUB infra
```
