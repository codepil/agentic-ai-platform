"""
Requirements node — runs the RequirementsCrew to produce user stories and AC.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from langchain_core.messages import AIMessage

from ...state.sdlc_state import SDLCState
from ...crews.requirements_crew import RequirementsCrew


async def requirements_node(state: SDLCState) -> Dict[str, Any]:
    """Run the requirements crew and update state with structured requirements."""
    t0 = time.time()

    crew = RequirementsCrew()
    result = crew.kickoff(
        inputs={
            "run_id": state["run_id"],
            "product_id": state["product_id"],
            "jira_epic_id": state["jira_epic_id"],
            "figma_url": state.get("figma_url", ""),
            "prd_s3_url": state.get("prd_s3_url", ""),
            "human_feedback": state.get("human_feedback", ""),
        }
    )

    elapsed = time.time() - t0
    timings = dict(state.get("stage_timings", {}))
    timings["requirements"] = elapsed

    n_stories = len(result.get("user_stories", []))
    n_criteria = len(result.get("acceptance_criteria", []))

    msg = AIMessage(
        content=(
            f"Requirements analysis complete in {elapsed:.2f}s. "
            f"Produced {n_stories} user stories, {n_criteria} acceptance criteria, "
            f"SAP deps: {result.get('sap_dependencies', [])}. "
            f"Ambiguities flagged: {len(result.get('ambiguities', []))}. "
            f"Awaiting human approval."
        )
    )

    return {
        "requirements": result,
        "current_stage": "requirements_approval",
        "approval_status": None,
        "human_feedback": None,
        "messages": [msg],
        "stage_timings": timings,
    }
