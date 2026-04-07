"""
Architecture node — runs the ArchitectureCrew to produce system design artefacts.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from langchain_core.messages import AIMessage

from ...state.sdlc_state import SDLCState
from ...crews.architecture_crew import ArchitectureCrew


async def architecture_node(state: SDLCState) -> Dict[str, Any]:
    """Run the architecture crew and update state with design artefacts."""
    t0 = time.time()

    crew = ArchitectureCrew()
    result = crew.kickoff(
        inputs={
            "run_id": state["run_id"],
            "product_id": state["product_id"],
            "requirements": state.get("requirements", {}),
            "human_feedback": state.get("human_feedback", ""),
        }
    )

    elapsed = time.time() - t0
    timings = dict(state.get("stage_timings", {}))
    timings["architecture"] = elapsed

    n_specs = len(result.get("openapi_specs", []))
    n_schemas = len(result.get("mongodb_schemas", []))
    n_adrs = len(result.get("adr_ids", []))

    msg = AIMessage(
        content=(
            f"Architecture design complete in {elapsed:.2f}s. "
            f"Produced {n_specs} OpenAPI specs, {n_schemas} MongoDB schemas, "
            f"{n_adrs} ADRs. "
            f"SAP integration plan: {list(result.get('sap_integration_plan', {}).keys())}."
        )
    )

    return {
        "architecture": result,
        "current_stage": "dev",
        "approval_status": None,
        "human_feedback": None,
        "messages": [msg],
        "stage_timings": timings,
    }
