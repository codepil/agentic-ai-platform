# LangGraph — SDLC Workflow Deep Dive

**Parent:** [blueprint.md](../../blueprint.md)
**Section:** Agent Engine → LangGraph
**Status:** Done

---

## Overview

LangGraph provides the **stateful execution backbone** of the platform. Every SDLC run is a LangGraph graph execution. The graph defines nodes (agent tasks), edges (transitions), conditional routing (QA pass/fail, approval gates), and checkpoints (state saved to MongoDB Atlas after every node).

CrewAI crews are called **inside** LangGraph nodes — LangGraph owns the workflow, CrewAI owns the agent collaboration within each stage.

---

## Core Concepts Applied Here

| LangGraph Concept | How It's Used |
|-------------------|---------------|
| `StateGraph` | One graph per SDLC run, typed state flows through every node |
| `TypedDict` state | Carries all inputs, crew outputs, iteration counts, approval status |
| `Annotated` messages | Full message history accumulates across all nodes |
| `interrupt()` | Pauses graph at human approval gates; resumes on approval |
| `Command(resume=...)` | Java backend resumes graph after human approves/rejects |
| `MemorySaver` (custom) | MongoDB Atlas checkpointer — state saved after every node |
| Subgraphs | Each crew stage is a compiled subgraph, composable into main graph |
| Conditional edges | Route QA pass/fail, approval granted/rejected, iteration limits |

---

## SDLC State Definition

```python
# shared-python-libs/src/platform/state/sdlc_state.py

from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class LLMUsage(TypedDict):
    input_tokens: int
    output_tokens: int
    cost_usd: float


class RequirementsOutput(TypedDict):
    user_stories: list[dict]          # structured BDD user stories
    acceptance_criteria: list[dict]   # Gherkin scenarios
    sap_dependencies: list[str]       # SAP BAPI/OData calls needed
    ambiguities: list[str]            # flagged for human review
    jira_subtask_ids: list[str]       # created by agent in Jira


class ArchitectureOutput(TypedDict):
    openapi_specs: list[dict]         # one spec per microservice
    mongodb_schemas: list[dict]       # collection designs
    adr_ids: list[str]                # ADR document IDs in MongoDB
    sap_integration_plan: dict        # BAPI/OData mapping per service
    service_dependency_graph: dict    # which services call which


class CodeArtifact(TypedDict):
    artifact_id: str
    type: str                         # java_service | react_component | test | pipeline_yaml
    repo: str
    file_path: str
    git_branch: str
    git_commit_sha: str
    content_hash: str


class QAResults(TypedDict):
    passed: bool
    unit_test_results: dict
    integration_test_results: dict
    security_scan_results: dict
    code_review_findings: list[str]
    e2e_test_results: dict
    failure_summary: Optional[str]    # populated only on failure


class DeploymentResult(TypedDict):
    environment: str                  # staging | production
    service_urls: dict
    git_pr_url: str
    pipeline_run_url: str
    deployed_at: str                  # ISO datetime


class SDLCState(TypedDict):
    # Identity
    run_id: str
    product_id: str
    thread_id: str                    # LangGraph thread ID (maps to MongoDB doc)

    # Inputs
    jira_epic_id: str
    figma_url: Optional[str]
    prd_s3_url: Optional[str]

    # Stage outputs — None until that stage completes
    requirements: Optional[RequirementsOutput]
    architecture: Optional[ArchitectureOutput]
    code_artifacts: Optional[list[CodeArtifact]]
    qa_results: Optional[QAResults]
    deployment: Optional[DeploymentResult]

    # Control flow
    current_stage: str                # intake | requirements | architecture | dev | qa | devops | done
    qa_iteration: int                 # current QA retry count
    max_qa_iterations: int            # default: 3
    approval_status: str              # pending | approved | rejected | not_required
    human_feedback: Optional[str]     # populated when human rejects

    # Accumulated message history (all agent reasoning chains)
    messages: Annotated[list[BaseMessage], add_messages]

    # Observability
    llm_usage: LLMUsage
    errors: list[str]
    stage_timings: dict               # stage_name -> duration_seconds
```

---

## Main SDLC Graph

```python
# agent-engine/src/graphs/sdlc_graph.py

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.base import BaseCheckpointSaver
from platform.state.sdlc_state import SDLCState
from graphs.nodes import (
    intake_node,
    requirements_node,
    requirements_approval_node,
    architecture_node,
    dev_node,
    qa_node,
    qa_failed_handler_node,
    devops_node,
    staging_approval_node,
    deploy_prod_node,
    error_handler_node,
)
from graphs.edges import (
    route_after_requirements_approval,
    route_after_qa,
    route_after_staging_approval,
    route_on_error,
)


def build_sdlc_graph(checkpointer: BaseCheckpointSaver) -> CompiledGraph:
    graph = StateGraph(SDLCState)

    # --- Register nodes ---
    graph.add_node("intake",                intake_node)
    graph.add_node("requirements",          requirements_node)
    graph.add_node("requirements_approval", requirements_approval_node)   # interrupt
    graph.add_node("architecture",          architecture_node)
    graph.add_node("dev",                   dev_node)
    graph.add_node("qa",                    qa_node)
    graph.add_node("qa_failed_handler",     qa_failed_handler_node)
    graph.add_node("devops",                devops_node)
    graph.add_node("staging_approval",      staging_approval_node)        # interrupt
    graph.add_node("deploy_prod",           deploy_prod_node)
    graph.add_node("error_handler",         error_handler_node)

    # --- Entry point ---
    graph.set_entry_point("intake")

    # --- Direct edges ---
    graph.add_edge("intake",           "requirements")
    graph.add_edge("requirements",     "requirements_approval")
    graph.add_edge("architecture",     "dev")
    graph.add_edge("dev",              "qa")
    graph.add_edge("qa_failed_handler","dev")
    graph.add_edge("devops",           "staging_approval")
    graph.add_edge("deploy_prod",      END)
    graph.add_edge("error_handler",    END)

    # --- Conditional edges ---
    graph.add_conditional_edges(
        "requirements_approval",
        route_after_requirements_approval,
        {
            "approved":    "architecture",
            "rejected":    "requirements",   # re-run with human feedback
            "escalate":    "error_handler",  # max rejections reached
        }
    )

    graph.add_conditional_edges(
        "qa",
        route_after_qa,
        {
            "passed":      "devops",
            "retry":       "qa_failed_handler",
            "escalate":    "error_handler",  # max iterations exceeded
        }
    )

    graph.add_conditional_edges(
        "staging_approval",
        route_after_staging_approval,
        {
            "approved":    "deploy_prod",
            "rejected":    "dev",            # back to dev with staging feedback
            "escalate":    "error_handler",
        }
    )

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["requirements_approval", "staging_approval"]
    )
```

---

## Node Definitions

### intake_node
```python
# graphs/nodes/intake_node.py

async def intake_node(state: SDLCState) -> dict:
    """
    Parse all inputs. Validate Jira epic exists, Figma URL is accessible,
    PRD S3 object exists. Enrich state with parsed context.
    """
    jira_client = get_jira_client()
    epic = await jira_client.get_epic(state["jira_epic_id"])

    figma_meta = None
    if state.get("figma_url"):
        figma_meta = await get_figma_client().get_file_metadata(state["figma_url"])

    prd_text = None
    if state.get("prd_s3_url"):
        prd_text = await s3_client.read_text(state["prd_s3_url"])

    return {
        "current_stage": "intake_complete",
        "messages": [
            SystemMessage(content=f"SDLC run started. Epic: {epic['summary']}"),
            HumanMessage(content=build_intake_summary(epic, figma_meta, prd_text))
        ]
    }
```

### requirements_node
```python
# graphs/nodes/requirements_node.py

async def requirements_node(state: SDLCState) -> dict:
    """
    Invoke Requirements Crew via CrewAI.
    Crew reads Jira epic, Figma metadata, PRD text from state messages.
    Writes sub-tasks back to Jira. Returns structured RequirementsOutput.
    """
    crew = RequirementsCrew()
    result: RequirementsOutput = await crew.kickoff(inputs={
        "run_id":        state["run_id"],
        "jira_epic_id":  state["jira_epic_id"],
        "messages":      state["messages"],
        "human_feedback": state.get("human_feedback"),  # populated on retry
    })

    return {
        "requirements":    result,
        "current_stage":   "requirements_complete",
        "human_feedback":  None,              # clear after use
        "approval_status": "pending",
        "llm_usage":       accumulate_usage(state["llm_usage"], result["usage"]),
        "messages": [
            AIMessage(content=f"Requirements complete. {len(result['user_stories'])} stories. "
                               f"Pending approval.")
        ]
    }
```

### requirements_approval_node
```python
# graphs/nodes/requirements_approval_node.py
from langgraph.types import interrupt

async def requirements_approval_node(state: SDLCState) -> dict:
    """
    Human gate. Graph pauses here via interrupt().
    Java backend detects 'waiting_approval' status in MongoDB,
    notifies approver via Slack + Web UI.
    Resumes when Java calls graph.invoke(Command(resume=approval_payload)).
    """
    # interrupt() pauses graph execution. Value passed is sent to the
    # Java backend via the checkpoint and surfaced in the approval portal.
    approval_payload = interrupt({
        "run_id":          state["run_id"],
        "stage":           "requirements",
        "artifact_summary": summarise_requirements(state["requirements"]),
        "jira_subtasks":   state["requirements"]["jira_subtask_ids"],
        "ambiguities":     state["requirements"]["ambiguities"],
    })

    # Execution resumes here after human acts. approval_payload is the
    # value passed in Command(resume=...) by the Java backend.
    return {
        "approval_status": approval_payload["decision"],   # "approved" | "rejected"
        "human_feedback":  approval_payload.get("feedback"),
        "current_stage":   "requirements_reviewed",
        "messages": [
            HumanMessage(content=f"Approval decision: {approval_payload['decision']}. "
                                  f"Feedback: {approval_payload.get('feedback', 'none')}")
        ]
    }
```

### architecture_node
```python
async def architecture_node(state: SDLCState) -> dict:
    crew = ArchitectureCrew()
    result: ArchitectureOutput = await crew.kickoff(inputs={
        "run_id":        state["run_id"],
        "requirements":  state["requirements"],
        "messages":      state["messages"],
    })

    return {
        "architecture":  result,
        "current_stage": "architecture_complete",
        "llm_usage":     accumulate_usage(state["llm_usage"], result["usage"]),
        "messages": [
            AIMessage(content=f"Architecture complete. "
                               f"{len(result['openapi_specs'])} OpenAPI specs generated. "
                               f"{len(result['adr_ids'])} ADRs written.")
        ]
    }
```

### dev_node
```python
async def dev_node(state: SDLCState) -> dict:
    crew = DevCrew()
    result: list[CodeArtifact] = await crew.kickoff(inputs={
        "run_id":          state["run_id"],
        "architecture":    state["architecture"],
        "qa_results":      state.get("qa_results"),      # populated on retry
        "human_feedback":  state.get("human_feedback"),  # populated on staging rejection
        "messages":        state["messages"],
    })

    return {
        "code_artifacts": result,
        "current_stage":  "dev_complete",
        "qa_results":     None,              # clear previous QA results on re-run
        "llm_usage":      accumulate_usage(state["llm_usage"], {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0}),
        "messages": [
            AIMessage(content=f"Dev complete. {len(result)} artifacts committed to feature branch.")
        ]
    }
```

### qa_node
```python
async def qa_node(state: SDLCState) -> dict:
    crew = QACrew()
    result: QAResults = await crew.kickoff(inputs={
        "run_id":         state["run_id"],
        "code_artifacts": state["code_artifacts"],
        "architecture":   state["architecture"],
        "messages":       state["messages"],
    })

    return {
        "qa_results":    result,
        "current_stage": "qa_complete",
        "qa_iteration":  state["qa_iteration"] + (0 if result["passed"] else 1),
        "messages": [
            AIMessage(content=f"QA {'passed' if result['passed'] else 'failed'}. "
                               f"Iteration {state['qa_iteration'] + 1}/{state['max_qa_iterations']}.")
        ]
    }
```

### qa_failed_handler_node
```python
async def qa_failed_handler_node(state: SDLCState) -> dict:
    """
    Prepares context for Dev Crew retry. Summarises QA failures
    into actionable feedback. Does not call any LLM directly.
    """
    summary = build_qa_failure_summary(state["qa_results"])

    return {
        "current_stage":  "qa_failed_retry",
        "human_feedback": summary,   # reuse human_feedback field as dev retry context
        "messages": [
            SystemMessage(content=f"QA failed. Sending back to Dev Crew. "
                                   f"Failure summary: {summary}")
        ]
    }
```

### devops_node
```python
async def devops_node(state: SDLCState) -> dict:
    crew = DevOpsCrew()
    result: DeploymentResult = await crew.kickoff(inputs={
        "run_id":         state["run_id"],
        "code_artifacts": state["code_artifacts"],
        "architecture":   state["architecture"],
        "messages":       state["messages"],
    })

    return {
        "deployment":    result,
        "current_stage": "deployed_staging",
        "approval_status": "pending",
        "messages": [
            AIMessage(content=f"Deployed to staging. PR: {result['git_pr_url']}. "
                               f"Pipeline: {result['pipeline_run_url']}")
        ]
    }
```

### staging_approval_node
```python
async def staging_approval_node(state: SDLCState) -> dict:
    """Second human gate — staging to production promotion."""
    approval_payload = interrupt({
        "run_id":        state["run_id"],
        "stage":         "staging",
        "staging_url":   state["deployment"]["service_urls"],
        "pr_url":        state["deployment"]["git_pr_url"],
        "pipeline_url":  state["deployment"]["pipeline_run_url"],
    })

    return {
        "approval_status": approval_payload["decision"],
        "human_feedback":  approval_payload.get("feedback"),
        "current_stage":   "staging_reviewed",
        "messages": [
            HumanMessage(content=f"Staging approval: {approval_payload['decision']}.")
        ]
    }
```

---

## Conditional Edge Functions

```python
# graphs/edges/routing.py

def route_after_requirements_approval(state: SDLCState) -> str:
    approval = state["approval_status"]
    rejection_count = state.get("requirements_rejection_count", 0)

    if approval == "approved":
        return "approved"
    elif approval == "rejected" and rejection_count < 2:
        return "rejected"
    else:
        return "escalate"   # 2 rejections → human escalation, stop graph


def route_after_qa(state: SDLCState) -> str:
    qa = state["qa_results"]
    iteration = state["qa_iteration"]
    max_iter = state["max_qa_iterations"]

    if qa["passed"]:
        return "passed"
    elif iteration < max_iter:
        return "retry"
    else:
        return "escalate"   # max retries hit → notify team, stop graph


def route_after_staging_approval(state: SDLCState) -> str:
    approval = state["approval_status"]

    if approval == "approved":
        return "approved"
    elif approval == "rejected":
        return "rejected"   # back to dev with staging feedback
    else:
        return "escalate"
```

---

## MongoDB Atlas Checkpointer

LangGraph ships with SQLite and PostgreSQL checkpointers. We implement a custom MongoDB checkpointer to keep state in Atlas alongside all other platform data.

```python
# shared-python-libs/src/platform/checkpointing/mongo_checkpointer.py

from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata
from pymongo import MongoClient
from typing import Iterator, Optional
import json


class MongoCheckpointer(BaseCheckpointSaver):
    """
    Persists LangGraph checkpoints to MongoDB Atlas.
    Collection: agent_runs (langgraph_checkpoint sub-document)
    Each checkpoint = one node completion event.
    """

    def __init__(self, mongo_uri: str, db_name: str):
        self.collection = MongoClient(mongo_uri)[db_name]["langgraph_checkpoints"]
        # Indexes: thread_id + checkpoint_id for fast lookup
        self.collection.create_index([("thread_id", 1), ("checkpoint_id", -1)])
        self.collection.create_index([("thread_id", 1), ("checkpoint_ts", -1)])

    def put(
        self,
        config: dict,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: dict,
    ) -> dict:
        thread_id = config["configurable"]["thread_id"]
        doc = {
            "thread_id":     thread_id,
            "checkpoint_id": checkpoint["id"],
            "checkpoint_ts": checkpoint["ts"],
            "checkpoint":    checkpoint,
            "metadata":      metadata,
            "new_versions":  new_versions,
        }
        self.collection.insert_one(doc)
        return config

    def get_tuple(self, config: dict) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = config["configurable"].get("checkpoint_id")

        query = {"thread_id": thread_id}
        if checkpoint_id:
            query["checkpoint_id"] = checkpoint_id

        doc = self.collection.find_one(query, sort=[("checkpoint_ts", -1)])
        if not doc:
            return None

        return CheckpointTuple(
            config=config,
            checkpoint=doc["checkpoint"],
            metadata=doc["metadata"],
        )

    def list(self, config: dict, *, limit: Optional[int] = None) -> Iterator[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        cursor = self.collection.find(
            {"thread_id": thread_id},
            sort=[("checkpoint_ts", -1)],
            limit=limit or 0
        )
        for doc in cursor:
            yield CheckpointTuple(
                config={"configurable": {"thread_id": thread_id,
                                         "checkpoint_id": doc["checkpoint_id"]}},
                checkpoint=doc["checkpoint"],
                metadata=doc["metadata"],
            )
```

---

## Java Backend — Resuming the Graph After Human Approval

All communication between Java (Spring Boot) and Python (FastAPI) is HTTP/1.1 REST.
Agent event streaming uses Server-Sent Events (SSE) — Java subscribes to the Python SSE endpoint
and forwards events to ReactJS clients via WebSocket (STOMP).

### Python FastAPI — REST + SSE Server

```python
# agent-engine: src/platform/api/server.py

import asyncio
import json
import time
import uuid
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..graphs.sdlc_graph import build_sdlc_graph
from ..state.sdlc_state import SDLCState, default_llm_usage
from ..checkpointing.mongo_checkpointer import MongoCheckpointer
from ..config import settings

app = FastAPI(title="Agent Engine", version="1.0.0")

# One shared graph instance — thread_id isolates each SDLC run
checkpointer = MongoCheckpointer(settings.mongo_uri, settings.mongo_db_name)
graph = build_sdlc_graph(checkpointer)

# In-memory event queues per run_id (backed by MongoDB in production)
_event_queues: dict[str, asyncio.Queue] = {}


class StartRunRequest(BaseModel):
    run_id: str
    thread_id: str
    jira_epic_id: str
    product_id: str
    figma_url: str | None = None
    prd_s3_url: str | None = None
    max_qa_iterations: int = 3


class ResumeRunRequest(BaseModel):
    decision: str       # "approved" | "rejected"
    feedback: str | None = None
    approved_by: str


@app.post("/api/v1/runs", status_code=202)
async def start_run(req: StartRunRequest, background_tasks: BackgroundTasks):
    """Start a new SDLC run. Runs the graph asynchronously."""
    initial_state = SDLCState(
        run_id=req.run_id,
        product_id=req.product_id,
        thread_id=req.thread_id,
        jira_epic_id=req.jira_epic_id,
        figma_url=req.figma_url,
        prd_s3_url=req.prd_s3_url,
        requirements=None,
        architecture=None,
        code_artifacts=[],
        qa_results=None,
        deployment=None,
        current_stage="intake",
        qa_iteration=0,
        max_qa_iterations=req.max_qa_iterations,
        approval_status=None,
        human_feedback=None,
        requirements_rejection_count=0,
        messages=[],
        llm_usage=default_llm_usage(),
        errors=[],
        stage_timings={},
    )
    _event_queues[req.run_id] = asyncio.Queue()
    config = {"configurable": {"thread_id": req.thread_id}}
    background_tasks.add_task(_run_graph, req.run_id, initial_state, config)
    return {"run_id": req.run_id, "status": "started"}


@app.post("/api/v1/runs/{run_id}/resume", status_code=202)
async def resume_run(run_id: str, req: ResumeRunRequest, background_tasks: BackgroundTasks):
    """Resume a graph paused at a human approval gate."""
    from langgraph.types import Command

    # Retrieve thread_id from MongoDB checkpoint
    snapshot = _get_snapshot(run_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    thread_id = snapshot.config["configurable"]["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}
    resume_payload = {"decision": req.decision, "feedback": req.feedback}

    if run_id not in _event_queues:
        _event_queues[run_id] = asyncio.Queue()

    background_tasks.add_task(
        _resume_graph, run_id, Command(resume=resume_payload), config
    )
    return {"run_id": run_id, "status": "resuming"}


@app.get("/api/v1/runs/{run_id}/events")
async def stream_events(run_id: str):
    """SSE endpoint — streams agent events as the graph executes."""
    if run_id not in _event_queues:
        raise HTTPException(status_code=404, detail=f"No event stream for run {run_id}")

    async def event_generator() -> AsyncIterator[str]:
        queue = _event_queues[run_id]
        while True:
            event = await asyncio.wait_for(queue.get(), timeout=300)
            if event is None:           # sentinel — run finished
                yield "data: {\"event_type\": \"run_complete\"}\n\n"
                break
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/v1/runs/{run_id}/status")
async def get_status(run_id: str):
    """Poll the current status of a run from the checkpoint."""
    snapshot = _get_snapshot(run_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    state = snapshot.values
    return {
        "run_id":        run_id,
        "current_stage": state.get("current_stage"),
        "next_nodes":    list(snapshot.next),
        "qa_iteration":  state.get("qa_iteration", 0),
        "llm_usage":     state.get("llm_usage"),
        "errors":        state.get("errors", []),
    }


@app.delete("/api/v1/runs/{run_id}", status_code=204)
async def cancel_run(run_id: str):
    """Cancel a run by draining its event queue with a sentinel."""
    queue = _event_queues.pop(run_id, None)
    if queue:
        await queue.put(None)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _run_graph(run_id: str, initial_state: SDLCState, config: dict):
    queue = _event_queues[run_id]
    try:
        async for event in graph.astream(initial_state, config=config, stream_mode="updates"):
            await queue.put(_to_sse_event(run_id, event))
    except Exception as exc:
        await queue.put({"run_id": run_id, "event_type": "error", "payload": str(exc), "ts": _ts()})
    finally:
        await queue.put(None)   # sentinel


async def _resume_graph(run_id: str, command, config: dict):
    queue = _event_queues[run_id]
    try:
        async for event in graph.astream(command, config=config, stream_mode="updates"):
            await queue.put(_to_sse_event(run_id, event))
    except Exception as exc:
        await queue.put({"run_id": run_id, "event_type": "error", "payload": str(exc), "ts": _ts()})
    finally:
        await queue.put(None)


def _to_sse_event(run_id: str, event: dict) -> dict:
    node = next(iter(event), "")
    state_update = event.get(node, {})
    return {
        "run_id":     run_id,
        "agent":      node,
        "event_type": "state_update",
        "payload":    state_update.get("current_stage", ""),
        "ts":         _ts(),
    }


def _ts() -> int:
    return int(time.time() * 1000)


def _get_snapshot(run_id: str):
    # Scan checkpoints to find the thread_id for this run_id
    # In production: look up run_id → thread_id in agent_runs MongoDB collection
    # For now thread_id == run_id (see StartRunRequest)
    config = {"configurable": {"thread_id": run_id}}
    try:
        return graph.get_state(config)
    except Exception:
        return None
```

### Java Spring Boot — Calling the Agent Engine

```java
// platform-core: AgentRunService.java

@Service
public class AgentRunService {

    private final WebClient agentEngineClient;   // Spring WebClient (non-blocking)
    private final AgentRunRepository runRepository;
    private final WebSocketBroadcaster webSocketBroadcaster;
    private final AuditTrailService auditTrailService;
    private final SlackNotificationService slack;

    public AgentRunService(
            @Value("${agent.engine.base-url}") String agentEngineUrl,
            AgentRunRepository runRepository,
            WebSocketBroadcaster webSocketBroadcaster,
            AuditTrailService auditTrailService,
            SlackNotificationService slack) {
        this.agentEngineClient = WebClient.builder()
            .baseUrl(agentEngineUrl)
            .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
            .build();
        this.runRepository = runRepository;
        this.webSocketBroadcaster = webSocketBroadcaster;
        this.auditTrailService = auditTrailService;
        this.slack = slack;
    }

    /**
     * Starts a new SDLC run by calling POST /api/v1/runs on the agent engine,
     * then subscribes to the SSE event stream and forwards events to the
     * ReactJS dashboard via WebSocket.
     */
    public void startRun(StartRunCommand cmd) {
        String runId = cmd.getRunId();

        // 1. Kick off the run
        agentEngineClient.post()
            .uri("/api/v1/runs")
            .bodyValue(buildStartRunRequest(cmd))
            .retrieve()
            .bodyToMono(Map.class)
            .subscribe(response -> subscribeToEventStream(runId));
    }

    /**
     * Called by the approval portal MFE when a human approves or rejects.
     * Sends a REST resume request to the Python agent engine.
     */
    public void processApproval(String runId, ApprovalDecision decision) {
        AgentRun run = runRepository.findByRunId(runId)
            .orElseThrow(() -> new RunNotFoundException(runId));

        if (!run.getStatus().equals("waiting_approval")) {
            throw new InvalidRunStateException("Run is not awaiting approval");
        }

        Map<String, Object> body = Map.of(
            "decision",    decision.getDecision(),       // "approved" | "rejected"
            "feedback",    decision.getFeedback() != null ? decision.getFeedback() : "",
            "approved_by", decision.getApprovedBy()      // Okta user ID
        );

        agentEngineClient.post()
            .uri("/api/v1/runs/{runId}/resume", runId)
            .bodyValue(body)
            .retrieve()
            .bodyToMono(Map.class)
            .subscribe(response -> subscribeToEventStream(runId));
    }

    /**
     * Subscribe to the SSE event stream from the Python agent engine.
     * Each event is broadcast to WebSocket subscribers and persisted to audit_trail.
     */
    private void subscribeToEventStream(String runId) {
        agentEngineClient.get()
            .uri("/api/v1/runs/{runId}/events", runId)
            .accept(MediaType.TEXT_EVENT_STREAM)
            .retrieve()
            .bodyToFlux(String.class)          // each SSE data line
            .doOnNext(rawEvent -> {
                webSocketBroadcaster.broadcast(runId, rawEvent);
                auditTrailService.record(runId, rawEvent);
            })
            .doOnError(t -> {
                runRepository.updateStatus(runId, "failed");
                slack.alertOncall(runId, "Agent engine stream error: " + t.getMessage());
            })
            .doOnComplete(() -> runRepository.updateStatus(runId, "completed"))
            .subscribe();
    }
}
```

---

## Full Graph Flow Diagram

```
[START]
   │
   ▼
[intake_node]
   │  Parses Jira epic, Figma metadata, PRD text
   │
   ▼
[requirements_node]  ◄──────────────────────────────────────┐
   │  Requirements Crew generates user stories,              │
   │  acceptance criteria, SAP deps, Jira sub-tasks          │
   │                                                         │
   ▼                                                         │ rejected
[requirements_approval_node]  ←── INTERRUPT (human gate)    │
   │                                                         │
   ├─ approved ────────────────────────────────────────────► ▼
   │                                                    [architecture_node]
   └─ rejected ──────────────────────────────────────────────┘
   │
   │ (escalate if 2+ rejections)
   ▼
[error_handler_node] ──► [END]


[architecture_node]
   │  Architecture Crew generates OpenAPI specs,
   │  MongoDB schemas, ADRs, SAP integration plan
   │
   ▼
[dev_node]  ◄──────────────────────────────────────────────┐
   │  Dev Crew generates ReactJS, Java, MongoDB,            │
   │  SAP connector code. Commits to feature branch.        │
   │                                                        │
   ▼                                                        │ retry (with QA failure summary)
[qa_node]                                                   │
   │  QA Crew runs unit tests, integration tests,           │
   │  security scan, code review, E2E tests                 │
   │                                                        │
   ├─ failed + iterations < max ── [qa_failed_handler] ──►──┘
   │
   ├─ failed + max iterations hit
   │      └──► [error_handler_node] ──► [END]
   │
   └─ passed
         │
         ▼
      [devops_node]
         │  DevOps Crew generates CI/CD pipeline,
         │  deploys to staging, creates PR
         │
         ▼
      [staging_approval_node]  ←── INTERRUPT (human gate)
         │
         ├─ approved ──► [deploy_prod_node] ──► [END]
         │
         └─ rejected ──► [dev_node]  (back to dev with staging feedback)
```

---

## LangGraph Run Lifecycle in MongoDB

```javascript
// langgraph_checkpoints collection — one doc per node completion
{
  thread_id: "thread-uuid",         // = run_id, links to agent_runs
  checkpoint_id: "chk-uuid",
  checkpoint_ts: "2026-04-07T10:23:00Z",
  checkpoint: {
    id: "chk-uuid",
    ts: "2026-04-07T10:23:00Z",
    channel_values: {               // full SDLCState at this checkpoint
      run_id: "...",
      current_stage: "requirements_complete",
      requirements: { ... },
      messages: [ ... ],
      llm_usage: { ... },
      // ... all state fields
    }
  },
  metadata: {
    source: "loop",
    step: 2,
    writes: { "requirements": { ... } }
  }
}

// agent_runs collection — high-level run status (Java-facing)
{
  run_id: "uuid",
  thread_id: "thread-uuid",         // foreign key to langgraph_checkpoints
  status: "waiting_approval",       // Java backend reads this
  current_stage: "requirements_complete",
  approval_stage: "requirements",   // which gate is open
  llm_usage: { input_tokens: 8500, output_tokens: 3200, cost_usd: 0.12 },
  qa_iteration: 0,
  started_at: ISODate,
  updated_at: ISODate
}
```

---

## Concurrency — Multiple Parallel SDLC Runs

Each SDLC run has its own `thread_id`. LangGraph is stateless at the graph level — state lives entirely in the MongoDB checkpointer. The Python agent engine can run multiple graphs concurrently.

```python
# agent-engine: run_manager.py

import asyncio
from typing import dict

active_runs: dict[str, asyncio.Task] = {}

async def start_run(run_id: str, thread_id: str, inputs: SDLCState):
    config = {"configurable": {"thread_id": thread_id}}
    task = asyncio.create_task(
        graph.ainvoke(inputs, config=config)
    )
    active_runs[run_id] = task
    return task

async def cancel_run(run_id: str):
    task = active_runs.get(run_id)
    if task:
        task.cancel()
        del active_runs[run_id]
```

---

## Token Cost Routing Strategy

Not every agent task needs Claude Sonnet 4.5. Route by complexity to minimise cost.

| Task | Model | Rationale |
|------|-------|-----------|
| Parsing Jira epic fields | Haiku | Structured extraction, no reasoning needed |
| Generating BDD acceptance criteria | Sonnet 4.5 | Requires understanding, context |
| OpenAPI spec generation | Sonnet 4.5 | Complex, must be accurate |
| MongoDB schema design | Sonnet 4.5 | Domain reasoning required |
| Java Spring Boot code generation | Sonnet 4.5 | Large context, complex output |
| ReactJS component generation | Sonnet 4.5 | Figma context + code output |
| Formatting/summarising QA results | Haiku | Simple transform |
| Security scan interpretation | Sonnet 4.5 | Must reason about CVEs |
| CI/CD YAML generation | Haiku | Template-like, low reasoning |
| Generating Terraform boilerplate | Haiku | Highly templated |
| Failure summary for Dev Crew retry | Haiku | Summarisation only |

```python
# shared-python-libs/src/platform/llm/model_router.py

from anthropic import Anthropic

SONNET = "claude-sonnet-4-5"
HAIKU  = "claude-haiku-4-5-20251001"

TASK_MODEL_MAP = {
    "parse_jira":            HAIKU,
    "write_acceptance_bdd":  SONNET,
    "generate_openapi":      SONNET,
    "design_mongo_schema":   SONNET,
    "generate_java_service": SONNET,
    "generate_react_mfe":    SONNET,
    "summarise_qa":          HAIKU,
    "interpret_security":    SONNET,
    "generate_cicd_yaml":    HAIKU,
    "generate_terraform":    HAIKU,
    "summarise_failure":     HAIKU,
}

def get_model_for_task(task_name: str) -> str:
    return TASK_MODEL_MAP.get(task_name, SONNET)  # default to Sonnet if unknown
```

---

## Error Handling & Observability

```python
# graphs/nodes/error_handler_node.py

async def error_handler_node(state: SDLCState) -> dict:
    """
    Terminal node for unrecoverable states.
    Logs full state to audit_trail. Notifies team via Slack.
    """
    error_context = {
        "run_id":        state["run_id"],
        "stage":         state["current_stage"],
        "qa_iterations": state["qa_iteration"],
        "errors":        state["errors"],
        "last_message":  state["messages"][-1].content if state["messages"] else None,
    }

    await audit_trail_service.record_escalation(error_context)
    await slack_client.post_escalation_alert(error_context)

    return {
        "current_stage": "escalated",
        "messages": [
            SystemMessage(content=f"Run {state['run_id']} escalated to human team. "
                                   f"Stage: {state['current_stage']}. "
                                   f"Errors: {state['errors']}")
        ]
    }
```

### Key Observability Points
| Event | Where Logged | Alert |
|-------|-------------|-------|
| Node start / complete | audit_trail + WebSocket | — |
| Human gate reached | audit_trail + Slack DM to approver | Slack |
| QA failure (each iteration) | audit_trail | — |
| Max iterations exceeded | audit_trail | Slack oncall |
| Graph error / exception | audit_trail | Slack oncall |
| LLM cost > $5 per run | llm_usage in agent_runs | Slack warning |
| Run duration > 2 hours | agent_runs updated_at diff | Slack warning |

---

## Next Deep Dives

- [ ] [crewai/requirements-crew.md](../crewai/requirements-crew.md) — Agent roles, system prompts, Jira + Figma tool bindings
- [ ] [crewai/dev-crew.md](../crewai/dev-crew.md) — Code generation agents, GitHub tool, OpenAPI → Java/React mapping
- [ ] [langgraph/state-schema.md](state-schema.md) — Full TypedDict definitions, validation, versioning
