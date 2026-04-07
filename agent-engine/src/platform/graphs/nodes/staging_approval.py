"""
Staging approval node — human-in-the-loop interrupt for production promotion.

The graph is compiled with ``interrupt_before=["staging_approval"]`` so
LangGraph pauses before this node.  The human reviewer inspects the staging
deployment and approves or rejects the production promotion.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from ...state.sdlc_state import SDLCState


async def staging_approval_node(state: SDLCState) -> Dict[str, Any]:
    """Pause for human approval of staging → production promotion."""
    t0 = time.time()

    deployment = state.get("deployment") or {}

    payload = {
        "stage": "staging_approval",
        "product_id": state["product_id"],
        "staging_urls": deployment.get("service_urls", {}),
        "git_pr_url": deployment.get("git_pr_url", ""),
        "pipeline_run_url": deployment.get("pipeline_run_url", ""),
        "deployed_at": deployment.get("deployed_at", ""),
        "instructions": (
            "Review the staging deployment above. "
            "Respond with {'decision': 'approved'|'rejected', 'feedback': str|None}"
        ),
    }

    resume_value: Dict[str, Any] = interrupt(payload)

    decision: str = resume_value.get("decision", "approved")
    feedback: str | None = resume_value.get("feedback")

    elapsed = time.time() - t0
    timings = dict(state.get("stage_timings", {}))
    timings["staging_approval"] = elapsed

    msg = AIMessage(
        content=(
            f"Staging approval: decision='{decision}'. "
            f"Feedback: {feedback or 'none'}."
        )
    )

    return {
        "approval_status": decision,
        "human_feedback": feedback,
        "current_stage": "staging_approval",
        "messages": [msg],
        "stage_timings": timings,
    }
