"""
main.py — Demonstrates a complete SDLC workflow run in MOCK_MODE.

Run:
    MOCK_MODE=true python3 main.py

The script:
1. Builds the SDLC graph with MemorySaver (no MongoDB needed in mock mode).
2. Defines an initial state for a fake Jira epic.
3. Streams the graph (async) until the first interrupt (requirements_approval).
4. Auto-approves requirements (simulating a human reviewer).
5. Continues streaming until the second interrupt (staging_approval).
6. Auto-approves staging promotion.
7. Continues streaming until the graph ends.
8. Prints a final state summary.
"""

from __future__ import annotations

import asyncio
import os
import uuid

# Ensure mock mode is active when running this demo
os.environ.setdefault("MOCK_MODE", "true")

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from src.platform.state.sdlc_state import SDLCState, default_llm_usage
from src.platform.graphs.sdlc_graph import build_sdlc_graph


def build_initial_state() -> SDLCState:
    """Return the initial SDLCState for the demo run."""
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    return SDLCState(
        run_id=run_id,
        product_id="SelfCare-001",
        thread_id=run_id,
        jira_epic_id="SC-42",
        figma_url="https://www.figma.com/file/DEMO1234/SelfCare-Catalog",
        prd_s3_url=None,
        requirements=None,
        architecture=None,
        code_artifacts=[],
        qa_results=None,
        deployment=None,
        current_stage="intake",
        qa_iteration=0,
        max_qa_iterations=3,
        approval_status=None,
        human_feedback=None,
        requirements_rejection_count=0,
        messages=[],
        llm_usage=default_llm_usage(),
        errors=[],
        stage_timings={},
    )


def print_separator(title: str) -> None:
    width = 70
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}\n")


async def run_sdlc_demo() -> None:
    """Execute a full SDLC run with auto-approval at each interrupt."""
    print_separator("SDLC Agentic Platform — Demo Run (MOCK_MODE)")

    checkpointer = MemorySaver()
    graph = build_sdlc_graph(checkpointer)

    initial_state = build_initial_state()
    thread_id = initial_state["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    print(f"Run ID    : {initial_state['run_id']}")
    print(f"Product   : {initial_state['product_id']}")
    print(f"Jira Epic : {initial_state['jira_epic_id']}\n")

    # ------------------------------------------------------------------
    # Phase 1: intake → requirements → INTERRUPT (requirements_approval)
    # ------------------------------------------------------------------
    print_separator("Phase 1: Intake → Requirements")

    async for event in graph.astream(initial_state, config=config, stream_mode="values"):
        stage = event.get("current_stage", "?")
        n_msgs = len(event.get("messages", []))
        print(f"  [stage={stage}] messages={n_msgs}")

    # Check if we hit an interrupt
    snapshot = graph.get_state(config)
    if snapshot.next:
        print(f"\n  Graph paused before: {snapshot.next}")
        print("  Auto-approving requirements...\n")

        async for event in graph.astream(
            Command(resume={"decision": "approved", "feedback": None}),
            config=config,
            stream_mode="values",
        ):
            stage = event.get("current_stage", "?")
            n_msgs = len(event.get("messages", []))
            print(f"  [stage={stage}] messages={n_msgs}")

    # ------------------------------------------------------------------
    # Phase 2: architecture → dev → qa → devops → INTERRUPT (staging_approval)
    # ------------------------------------------------------------------
    print_separator("Phase 2: Architecture → Dev → QA → DevOps")

    snapshot = graph.get_state(config)
    if snapshot.next:
        print(f"\n  Graph paused before: {snapshot.next}")
        print("  Auto-approving staging → production promotion...\n")

        async for event in graph.astream(
            Command(resume={"decision": "approved", "feedback": None}),
            config=config,
            stream_mode="values",
        ):
            stage = event.get("current_stage", "?")
            n_msgs = len(event.get("messages", []))
            print(f"  [stage={stage}] messages={n_msgs}")

    # ------------------------------------------------------------------
    # Final state summary
    # ------------------------------------------------------------------
    print_separator("Final State Summary")

    final_snapshot = graph.get_state(config)
    final: SDLCState = final_snapshot.values  # type: ignore[assignment]

    print(f"Run ID          : {final.get('run_id')}")
    print(f"Product         : {final.get('product_id')}")
    print(f"Final stage     : {final.get('current_stage')}")
    print(f"QA iterations   : {final.get('qa_iteration')}")
    print(f"Messages sent   : {len(final.get('messages', []))}")
    print(f"Errors          : {final.get('errors') or 'none'}")

    deployment = final.get("deployment") or {}
    print(f"\nDeployment:")
    print(f"  environment    : {deployment.get('environment', 'N/A')}")
    print(f"  PR URL         : {deployment.get('git_pr_url', 'N/A')}")
    print(f"  Pipeline URL   : {deployment.get('pipeline_run_url', 'N/A')}")
    print(f"  Services       : {list(deployment.get('service_urls', {}).keys())}")
    print(f"  Deployed at    : {deployment.get('deployed_at', 'N/A')}")

    timings = final.get("stage_timings", {})
    if timings:
        print("\nStage timings (seconds):")
        for stage, elapsed in timings.items():
            print(f"  {stage:<30} {elapsed:.3f}s")

    print_separator("SDLC Run Complete")


if __name__ == "__main__":
    asyncio.run(run_sdlc_demo())
