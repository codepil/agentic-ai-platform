"""
Requirements approval node — human-in-the-loop interrupt.

The graph is compiled with ``interrupt_before=["requirements_approval"]``
so LangGraph pauses BEFORE this node is called and waits for a ``Command``
resume value containing the human decision.

The ``interrupt()`` call inside this node provides the payload shown to
the human reviewer (summary of requirements to approve/reject).
When the graph is resumed via ``Command(resume=value)`` the interrupt()
call returns *value* — we extract the decision and feedback from it.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from ...state.sdlc_state import SDLCState


async def requirements_approval_node(state: SDLCState) -> Dict[str, Any]:
    """Pause for human approval of the generated requirements."""
    t0 = time.time()

    reqs = state.get("requirements") or {}
    n_stories = len(reqs.get("user_stories", []))
    n_criteria = len(reqs.get("acceptance_criteria", []))

    # Build the interrupt payload — this is what the human reviewer sees.
    payload = {
        "stage": "requirements_approval",
        "product_id": state["product_id"],
        "summary": (
            f"{n_stories} user stories, {n_criteria} acceptance criteria. "
            f"SAP deps: {reqs.get('sap_dependencies', [])}. "
            f"Ambiguities: {reqs.get('ambiguities', [])}."
        ),
        "requirements": reqs,
        "instructions": "Respond with {'decision': 'approved'|'rejected', 'feedback': str|None}",
    }

    # Pause and wait for the human.  resume_value is whatever the caller
    # passes in Command(resume=...) when resuming the graph.
    resume_value: Dict[str, Any] = interrupt(payload)

    decision: str = resume_value.get("decision", "approved")
    feedback: str | None = resume_value.get("feedback")

    elapsed = time.time() - t0
    timings = dict(state.get("stage_timings", {}))
    timings["requirements_approval"] = elapsed

    rejection_count = state.get("requirements_rejection_count", 0)
    if decision == "rejected":
        rejection_count += 1

    msg = AIMessage(
        content=(
            f"Requirements approval: decision='{decision}'. "
            f"Feedback: {feedback or 'none'}. "
            f"Rejection count: {rejection_count}."
        )
    )

    return {
        "approval_status": decision,
        "human_feedback": feedback,
        "requirements_rejection_count": rejection_count,
        "current_stage": "requirements_approval",
        "messages": [msg],
        "stage_timings": timings,
    }
