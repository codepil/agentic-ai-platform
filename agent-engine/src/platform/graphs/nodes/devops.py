"""
DevOps node — runs the DevOpsCrew to deploy to staging.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from langchain_core.messages import AIMessage

from ...state.sdlc_state import SDLCState
from ...crews.devops_crew import DevOpsCrew


async def devops_node(state: SDLCState) -> Dict[str, Any]:
    """Run the DevOps crew to deploy to staging and create a PR."""
    t0 = time.time()

    crew = DevOpsCrew()
    result = crew.kickoff(
        inputs={
            "run_id": state["run_id"],
            "product_id": state["product_id"],
            "code_artifacts": state.get("code_artifacts", []),
            "environment": "staging",
        }
    )

    elapsed = time.time() - t0
    timings = dict(state.get("stage_timings", {}))
    timings["devops"] = elapsed

    deployment = result.get("deployment", {})
    msg = AIMessage(
        content=(
            f"Staging deployment complete in {elapsed:.2f}s. "
            f"Environment: {deployment.get('environment', 'staging')}. "
            f"PR: {deployment.get('git_pr_url', 'N/A')}. "
            f"Pipeline: {deployment.get('pipeline_run_url', 'N/A')}. "
            f"Services: {list(deployment.get('service_urls', {}).keys())}. "
            f"Awaiting staging approval for production promotion."
        )
    )

    return {
        "deployment": deployment,
        "current_stage": "staging_approval",
        "approval_status": None,
        "messages": [msg],
        "stage_timings": timings,
    }
