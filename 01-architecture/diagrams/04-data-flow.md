# Data Flow Diagrams

These sequence diagrams trace the two principal runtime flows of the Agentic AI Platform: initiating a full SDLC automation run and resuming that run after a human approval decision. Together they capture the asynchronous, event-driven handoff between the React MFEs, the Java orchestration layer (`platform-app`), the Python agent runtime (`agent-engine`), LangGraph's stateful graph execution, and the external services that feed and are fed by the AI crews.

---

## Flow 1: Start SDLC Run

A user triggers an automated SDLC run from `mfe-agent-dashboard`. The platform-app orchestrates context enrichment, delegates execution to agent-engine, and then bridges the agent-engine SSE event stream back to the browser over WebSocket STOMP. The long-lived SSE connection between platform-app and agent-engine is highlighted with `activate`/`deactivate` blocks.

```mermaid
sequenceDiagram
    autonumber

    participant U as User
    participant MFE as ReactJS MFE<br/>(mfe-agent-dashboard)
    participant ALB as ALB
    participant PA as platform-app<br/>(Java)
    participant AE as agent-engine<br/>(Python)
    participant LG as LangGraph
    participant CC as CrewAI Crews
    participant DB as MongoDB Atlas
    participant ANT as Anthropic API<br/>(Claude Sonnet)
    participant EXT as External Systems<br/>(Jira / SAP / Figma)

    U->>MFE: Click "Start Run"
    MFE->>ALB: POST /api/v1/runs<br/>[Okta JWT in Authorization header]
    ALB->>PA: forward request

    Note over PA: RunController receives request

    PA->>PA: Validate Okta JWT<br/>(signature + claims)
    PA->>DB: INSERT AgentRun<br/>{ status: running }

    Note over PA,EXT: Parallel context enrichment

    par Fetch Jira epic
        PA->>EXT: GET /rest/agile/epic/{id}
        EXT-->>PA: epic metadata
    and Fetch SAP catalog
        PA->>EXT: GET /api/catalog/{id}
        EXT-->>PA: catalog data
    and Fetch Figma spec
        PA->>EXT: GET /v1/files/{key}
        EXT-->>PA: design spec
    end

    PA->>AE: POST /api/v1/runs<br/>{ runId, enrichedContext }

    Note over AE: Validates payload,<br/>schedules background task

    AE-->>PA: 202 Accepted<br/>{ runId }

    activate PA
    PA->>AE: GET /api/v1/runs/{id}/events<br/>(SSE, long-lived connection)
    Note over PA,AE: SSE stream open — platform-app<br/>will relay events to browser

    PA-->>MFE: 202 Accepted<br/>{ runId }
    MFE-->>U: Show "Run in progress" indicator

    AE->>LG: Execute graph(runId, context)
    activate LG

    LG->>CC: invoke requirements_crew

    activate CC
    CC->>ANT: Chat completion<br/>(system prompt + epic context)
    ANT-->>CC: User stories (Claude Sonnet response)
    CC-->>LG: RequirementsOutput
    deactivate CC

    LG->>DB: Save checkpoint<br/>{ stage: requirements, state: {...} }

    AE-->>PA: SSE event: state_update<br/>{ stage: "requirements", artifacts: [...] }
    PA-->>MFE: WebSocket STOMP frame<br/>{ event: state_update, stage: "requirements" }
    MFE-->>U: Dashboard updates — Requirements panel populated

    LG->>LG: Hit requirements_approval interrupt()

    Note over LG: Graph execution paused —<br/>awaiting human decision

    AE-->>PA: SSE event: approval_requested<br/>{ approvalId, stage: "requirements" }
    deactivate LG

    PA->>DB: INSERT ApprovalRequest<br/>{ status: pending, stage: requirements }
    PA->>PA: Send Slack notification<br/>(approval required)

    deactivate PA

    Note over MFE,PA: Run is now paused.<br/>PM must approve before execution resumes.
```

---

## Flow 2: Human Approval → Resume

A PM reviews the AI-generated requirements artifacts in `mfe-approval-portal` and submits an approval decision. The platform-app persists the decision, instructs agent-engine to resume the LangGraph graph from its saved checkpoint, re-opens the SSE bridge, and the remaining SDLC crews (architecture, dev, QA, DevOps) execute to completion.

```mermaid
sequenceDiagram
    autonumber

    participant PM as PM User
    participant AP as ReactJS MFE<br/>(mfe-approval-portal)
    participant ALB as ALB
    participant PA as platform-app<br/>(Java)
    participant AE as agent-engine<br/>(Python)
    participant LG as LangGraph
    participant DB as MongoDB Atlas

    PM->>AP: Open mfe-approval-portal<br/>(sees pending approval card)
    AP->>ALB: GET /api/v1/approvals?status=pending<br/>[Okta JWT]
    ALB->>PA: forward request
    PA->>DB: FIND ApprovalRequests { status: pending }
    DB-->>PA: [ ApprovalRequest ]
    PA-->>AP: 200 OK — approval list
    AP-->>PM: Render approval card with artifacts

    PM->>AP: Submit decision: Approved ✓
    AP->>ALB: POST /api/v1/approvals/{id}/decide<br/>{ decision: approved }<br/>[Okta JWT, scope: agents:approve]
    ALB->>PA: forward request

    Note over PA: ApprovalController → ApprovalService

    PA->>PA: Validate JWT scope<br/>agents:approve required

    PA->>DB: UPDATE ApprovalRequest<br/>{ status: approved, decidedBy: pm@co, decidedAt: now }

    activate PA
    PA->>AE: POST /api/v1/runs/{runId}/resume<br/>{ decision: approved, approvalId }

    Note over AE,LG: agent-engine restores graph<br/>from MongoDB checkpoint

    AE->>LG: Command(resume={ decision: "approved" })
    activate LG

    Note over LG: Graph resumes from<br/>requirements_approval interrupt

    PA->>AE: GET /api/v1/runs/{id}/events<br/>(SSE re-subscription)
    Note over PA,AE: SSE stream re-opened —<br/>platform-app bridges events to browser

    AE-->>PA: 200 OK — resume accepted

    LG->>LG: architecture_crew → design docs generated
    AE-->>PA: SSE event: state_update { stage: "architecture" }
    PA-->>AP: WebSocket STOMP frame { stage: "architecture" }

    LG->>LG: dev_crew → code artifacts generated
    AE-->>PA: SSE event: state_update { stage: "development" }
    PA-->>AP: WebSocket STOMP frame { stage: "development" }

    LG->>LG: qa_crew → test plan + results
    AE-->>PA: SSE event: state_update { stage: "qa" }
    PA-->>AP: WebSocket STOMP frame { stage: "qa" }

    LG->>LG: devops_crew → IaC + deploy pipeline
    AE-->>PA: SSE event: state_update { stage: "devops" }
    PA-->>AP: WebSocket STOMP frame { stage: "devops" }

    LG-->>AE: Graph execution complete
    deactivate LG

    AE-->>PA: SSE event: run_complete<br/>{ runId, artifactSummary }

    PA->>DB: UPDATE AgentRun<br/>{ status: completed, completedAt: now }
    PA->>PA: Send Slack success notification<br/>"SDLC Run {runId} completed"

    deactivate PA

    PA-->>AP: WebSocket STOMP frame { event: run_complete }
    AP-->>PM: Show "Run Complete" summary with all artifacts

    Note over PM,AP: Full SDLC cycle complete.<br/>All artifacts available for review.
```
