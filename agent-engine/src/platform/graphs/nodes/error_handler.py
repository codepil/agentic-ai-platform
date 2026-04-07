"""
Error handler node — escalates unrecoverable failures.

This node is reached when:
- Requirements are rejected more than ``max_requirements_rejections`` times
- QA fails more than ``max_qa_iterations`` times
- Any other critical failure pathway

It logs the escalation and sets ``current_stage = "escalated"`` so that
downstream monitoring can detect the workflow stall.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from langchain_core.messages import AIMessage

from ...state.sdlc_state import SDLCState


async def error_handler_node(state: SDLCState) -> Dict[str, Any]:
    """Log escalation details and mark the workflow as escalated."""
    t0 = time.time()

    errors = list(state.get("errors", []))
    qa_results = state.get("qa_results") or {}
    qa_iteration = state.get("qa_iteration", 0)
    max_iter = state.get("max_qa_iterations", 3)
    rejection_count = state.get("requirements_rejection_count", 0)

    escalation_reason = _determine_escalation_reason(
        errors, qa_results, qa_iteration, max_iter, rejection_count
    )

    escalation_msg = (
        f"ESCALATION REQUIRED for run '{state['run_id']}' "
        f"(product: {state['product_id']}). "
        f"Reason: {escalation_reason}. "
        f"Current stage: {state.get('current_stage', 'unknown')}. "
        f"QA iterations: {qa_iteration}/{max_iter}. "
        f"Requirements rejections: {rejection_count}. "
        f"Errors: {errors}."
    )
    errors.append(escalation_msg)

    elapsed = time.time() - t0
    timings = dict(state.get("stage_timings", {}))
    timings["error_handler"] = elapsed

    msg = AIMessage(
        content=(
            f"Workflow escalated. {escalation_reason}. "
            f"Human intervention required. "
            f"Run ID: {state['run_id']}."
        )
    )

    return {
        "current_stage": "escalated",
        "errors": errors,
        "messages": [msg],
        "stage_timings": timings,
    }


def _determine_escalation_reason(
    errors: list,
    qa_results: dict,
    qa_iteration: int,
    max_iter: int,
    rejection_count: int,
) -> str:
    if rejection_count >= 2:
        return f"Requirements rejected {rejection_count} times — unable to reach consensus"
    if qa_iteration >= max_iter and not qa_results.get("passed", False):
        return f"QA failed after {qa_iteration} iterations — code quality threshold not met"
    if errors:
        return f"Critical errors encountered: {errors[-1][:200]}"
    return "Unspecified escalation trigger"
