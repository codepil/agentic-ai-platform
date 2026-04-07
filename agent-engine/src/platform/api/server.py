"""
FastAPI REST server — exposes the LangGraph SDLC workflow over HTTP/1.1.

Endpoints
---------
POST   /api/v1/runs                   Start a new SDLC run
POST   /api/v1/runs/{run_id}/resume   Resume after a human approval gate
GET    /api/v1/runs/{run_id}/events   SSE stream of agent events
GET    /api/v1/runs/{run_id}/status   Poll current run status
DELETE /api/v1/runs/{run_id}          Cancel a running run

Java Spring Boot consumes these endpoints via WebClient.
The SSE stream is subscribed by Java and forwarded to ReactJS over WebSocket (STOMP).
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncIterator

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..checkpointing.mongo_checkpointer import MongoCheckpointer
from ..config import settings
from ..graphs.sdlc_graph import build_sdlc_graph
from ..state.sdlc_state import SDLCState, default_llm_usage
from langgraph.checkpoint.memory import MemorySaver

app = FastAPI(title="Agent Engine API", version="1.0.0")

# ---------------------------------------------------------------------------
# Graph — one instance, thread_id isolates each SDLC run in the checkpointer
# ---------------------------------------------------------------------------

def _build_checkpointer():
    if settings.mock_mode or not settings.mongo_uri:
        return MemorySaver()
    return MongoCheckpointer(settings.mongo_uri, settings.mongo_db_name)


_graph = build_sdlc_graph(_build_checkpointer())

# Per-run asyncio queues for SSE event delivery
_event_queues: dict[str, asyncio.Queue] = {}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class StartRunRequest(BaseModel):
    run_id: str
    thread_id: str
    jira_epic_id: str
    product_id: str
    figma_url: str | None = None
    prd_s3_url: str | None = None
    max_qa_iterations: int = 3


class ResumeRunRequest(BaseModel):
    decision: str           # "approved" | "rejected"
    feedback: str | None = None
    approved_by: str


class RunStatusResponse(BaseModel):
    run_id: str
    current_stage: str
    next_nodes: list[str]
    qa_iteration: int
    llm_usage: dict
    errors: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/runs", status_code=202)
async def start_run(req: StartRunRequest, background_tasks: BackgroundTasks):
    """
    Start a new SDLC run asynchronously.
    The graph executes in the background; subscribe to /events for live updates.
    """
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
    """
    Resume a graph paused at a human approval gate
    (requirements_approval or staging_approval).
    """
    from langgraph.types import Command

    snapshot = _get_snapshot(run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    if not snapshot.next:
        raise HTTPException(status_code=409, detail=f"Run '{run_id}' is not paused")

    config = snapshot.config
    resume_payload = {"decision": req.decision, "feedback": req.feedback}

    if run_id not in _event_queues:
        _event_queues[run_id] = asyncio.Queue()

    background_tasks.add_task(
        _resume_graph, run_id, Command(resume=resume_payload), config
    )
    return {"run_id": run_id, "status": "resuming"}


@app.get("/api/v1/runs/{run_id}/events")
async def stream_events(run_id: str):
    """
    Server-Sent Events stream of agent activity for a given run.

    Java Spring Boot subscribes here via WebClient and forwards events to
    the ReactJS dashboard over WebSocket (STOMP).
    """
    if run_id not in _event_queues:
        raise HTTPException(status_code=404, detail=f"No event stream for run '{run_id}'")

    async def _generator() -> AsyncIterator[str]:
        queue = _event_queues[run_id]
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=300)
            except asyncio.TimeoutError:
                yield "data: {\"event_type\": \"heartbeat\"}\n\n"
                continue
            if event is None:
                yield "data: {\"event_type\": \"run_complete\"}\n\n"
                break
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(_generator(), media_type="text/event-stream")


@app.get("/api/v1/runs/{run_id}/status", response_model=RunStatusResponse)
async def get_status(run_id: str):
    """Poll the current state of a run (no streaming required)."""
    snapshot = _get_snapshot(run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    state = snapshot.values
    return RunStatusResponse(
        run_id=run_id,
        current_stage=state.get("current_stage", "unknown"),
        next_nodes=list(snapshot.next),
        qa_iteration=state.get("qa_iteration", 0),
        llm_usage=state.get("llm_usage", {}),
        errors=state.get("errors", []),
    )


@app.delete("/api/v1/runs/{run_id}", status_code=204)
async def cancel_run(run_id: str):
    """Cancel a run by closing its event queue."""
    queue = _event_queues.pop(run_id, None)
    if queue:
        await queue.put(None)


# ---------------------------------------------------------------------------
# Background task helpers
# ---------------------------------------------------------------------------

async def _run_graph(run_id: str, initial_state: SDLCState, config: dict):
    queue = _event_queues.get(run_id)
    if queue is None:
        return
    try:
        async for event in _graph.astream(initial_state, config=config, stream_mode="updates"):
            await queue.put(_to_sse_payload(run_id, event))
    except Exception as exc:
        await queue.put({
            "run_id": run_id, "event_type": "error",
            "payload": str(exc), "ts": _now_ms(),
        })
    finally:
        await queue.put(None)


async def _resume_graph(run_id: str, command, config: dict):
    queue = _event_queues.get(run_id)
    if queue is None:
        return
    try:
        async for event in _graph.astream(command, config=config, stream_mode="updates"):
            await queue.put(_to_sse_payload(run_id, event))
    except Exception as exc:
        await queue.put({
            "run_id": run_id, "event_type": "error",
            "payload": str(exc), "ts": _now_ms(),
        })
    finally:
        await queue.put(None)


def _to_sse_payload(run_id: str, event: dict) -> dict:
    node = next(iter(event), "")
    state_update = event.get(node, {})
    return {
        "run_id":     run_id,
        "agent":      node,
        "event_type": "state_update",
        "stage":      state_update.get("current_stage", ""),
        "ts":         _now_ms(),
    }


def _get_snapshot(run_id: str):
    config = {"configurable": {"thread_id": run_id}}
    try:
        snapshot = _graph.get_state(config)
        # get_state returns an empty snapshot (not None) when thread is unknown
        return snapshot if snapshot.values else None
    except Exception:
        return None


def _now_ms() -> int:
    return int(time.time() * 1000)
