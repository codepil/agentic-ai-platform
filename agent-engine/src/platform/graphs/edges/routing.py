"""
Routing functions for conditional edges.

Each function receives the current SDLCState and returns a string route key
that LangGraph uses to select the next node.
"""

from __future__ import annotations

from typing import Literal

from ...state.sdlc_state import SDLCState

# Maximum consecutive requirements rejections before escalating
MAX_REQUIREMENTS_REJECTIONS = 2


def route_after_requirements_approval(
    state: SDLCState,
) -> Literal["approved", "rejected", "escalate"]:
    """
    Determine next step after requirements_approval.

    Returns
    -------
    "approved"  → proceed to architecture
    "rejected"  → loop back to requirements crew for rework
    "escalate"  → send to error_handler (too many rejections)
    """
    decision = state.get("approval_status", "approved")
    rejection_count = state.get("requirements_rejection_count", 0)

    if rejection_count >= MAX_REQUIREMENTS_REJECTIONS:
        return "escalate"

    if decision == "rejected":
        return "rejected"

    return "approved"


def route_after_qa(
    state: SDLCState,
) -> Literal["passed", "retry", "escalate"]:
    """
    Determine next step after qa node.

    Returns
    -------
    "passed"   → proceed to devops (staging deployment)
    "retry"    → route through qa_failed_handler then back to dev
    "escalate" → send to error_handler (max iterations exceeded)
    """
    qa_results = state.get("qa_results") or {}
    passed = qa_results.get("passed", False)
    iteration = state.get("qa_iteration", 0)
    max_iter = state.get("max_qa_iterations", 3)

    if passed:
        return "passed"

    if iteration < max_iter:
        return "retry"

    return "escalate"


def route_after_staging_approval(
    state: SDLCState,
) -> Literal["approved", "rejected", "escalate"]:
    """
    Determine next step after staging_approval.

    Returns
    -------
    "approved" → deploy to production
    "rejected" → loop back to dev crew for fixes
    "escalate" → send to error_handler
    """
    decision = state.get("approval_status", "approved")

    # Use qa_iteration as a proxy to detect infinite staging rejection loops.
    # After max_qa_iterations staging rejections we escalate.
    rejection_count = state.get("requirements_rejection_count", 0)
    if decision == "rejected" and rejection_count >= MAX_REQUIREMENTS_REJECTIONS:
        return "escalate"

    if decision == "rejected":
        return "rejected"

    return "approved"
