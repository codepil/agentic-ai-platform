"""
Dev node — runs the DevCrew to produce code artefacts.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from langchain_core.messages import AIMessage

from ...state.sdlc_state import SDLCState
from ...crews.dev_crew import DevCrew


async def dev_node(state: SDLCState) -> Dict[str, Any]:
    """Run the development crew and update state with code artefacts."""
    t0 = time.time()

    crew = DevCrew()
    result = crew.kickoff(
        inputs={
            "run_id": state["run_id"],
            "product_id": state["product_id"],
            "requirements": state.get("requirements", {}),
            "architecture": state.get("architecture", {}),
            "human_feedback": state.get("human_feedback", ""),
            "qa_iteration": state.get("qa_iteration", 0),
        }
    )

    elapsed = time.time() - t0
    timings = dict(state.get("stage_timings", {}))
    timings["dev"] = elapsed

    artifacts = result.get("code_artifacts", [])
    msg = AIMessage(
        content=(
            f"Development complete in {elapsed:.2f}s. "
            f"Produced {len(artifacts)} code artefacts: "
            f"{[a['type'] for a in artifacts]}."
        )
    )

    return {
        "code_artifacts": artifacts,
        "current_stage": "qa",
        "messages": [msg],
        "stage_timings": timings,
    }
