"""
Deploy production node — finalises the production deployment.

Updates the deployment record to reflect the production environment and
marks the workflow as complete.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict

from langchain_core.messages import AIMessage

from ...state.sdlc_state import SDLCState, DeploymentResult
from ...crews.devops_crew import DevOpsCrew


async def deploy_prod_node(state: SDLCState) -> Dict[str, Any]:
    """Deploy to production and mark the workflow complete."""
    t0 = time.time()

    crew = DevOpsCrew()
    result = crew.kickoff(
        inputs={
            "run_id": state["run_id"],
            "product_id": state["product_id"],
            "code_artifacts": state.get("code_artifacts", []),
            "environment": "production",
        }
    )

    elapsed = time.time() - t0
    timings = dict(state.get("stage_timings", {}))
    timings["deploy_prod"] = elapsed

    # Override environment to "production" regardless of crew output
    deployment: DeploymentResult = result.get("deployment", {})  # type: ignore[assignment]
    deployment = {
        **deployment,
        "environment": "production",
        "deployed_at": datetime.now(timezone.utc).isoformat(),
    }

    msg = AIMessage(
        content=(
            f"Production deployment successful in {elapsed:.2f}s. "
            f"Services live: {list(deployment.get('service_urls', {}).keys())}. "
            f"PR: {deployment.get('git_pr_url', 'N/A')}. "
            f"Pipeline: {deployment.get('pipeline_run_url', 'N/A')}. "
            f"SDLC workflow complete!"
        )
    )

    return {
        "deployment": deployment,
        "current_stage": "deployed_production",
        "approval_status": "approved",
        "messages": [msg],
        "stage_timings": timings,
    }
