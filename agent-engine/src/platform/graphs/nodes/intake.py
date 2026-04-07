"""
Intake node — validates inputs and enriches state with Jira / Figma data.

This is the first node in the graph. It:
1. Validates that required fields (jira_epic_id, product_id) are present.
2. Fetches the Jira epic metadata.
3. Fetches Figma component list if a Figma URL was supplied.
4. Appends a SystemMessage describing the project and a HumanMessage
   summarising the intake output.
5. Returns the enriched partial state.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ...state.sdlc_state import SDLCState
from ...tools.jira_tools import get_jira_client
from ...tools.figma_tools import get_figma_client


async def intake_node(state: SDLCState) -> Dict[str, Any]:
    """Validate inputs and enrich state from Jira and Figma."""
    t0 = time.time()

    errors: list[str] = list(state.get("errors", []))

    # --- Validate required fields ---
    missing = []
    for field in ("run_id", "product_id", "jira_epic_id"):
        if not state.get(field):
            missing.append(field)
    if missing:
        errors.append(f"Intake validation failed — missing fields: {missing}")

    # --- Fetch Jira epic ---
    jira = get_jira_client()
    epic_data: Dict[str, Any] = {}
    try:
        epic_data = jira.get_epic(state["jira_epic_id"])
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Jira fetch failed: {exc}")

    # --- Fetch Figma components ---
    figma_components: list[dict] = []
    figma_url: str = state.get("figma_url") or ""
    if figma_url:
        figma = get_figma_client()
        # Extract file key from URL like https://www.figma.com/file/<KEY>/...
        try:
            file_key = figma_url.rstrip("/").split("/file/")[-1].split("/")[0]
            figma_components = figma.list_components(file_key)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Figma fetch failed: {exc}")

    elapsed = time.time() - t0

    # --- Build messages ---
    system_msg = SystemMessage(
        content=(
            f"You are an autonomous SDLC agent for product '{state['product_id']}'. "
            f"Jira epic: {state['jira_epic_id']} — {epic_data.get('summary', 'N/A')}. "
            f"Full description: {epic_data.get('description', 'N/A')[:300]}."
        )
    )
    human_msg = HumanMessage(
        content=(
            f"Intake complete for run {state['run_id']}. "
            f"Epic '{epic_data.get('summary', 'N/A')}' fetched from Jira. "
            f"{len(figma_components)} Figma components loaded. "
            f"Errors so far: {errors or 'none'}."
        )
    )
    ai_msg = AIMessage(
        content=(
            f"Intake stage complete in {elapsed:.2f}s. "
            f"Product: {state['product_id']} | Epic: {state['jira_epic_id']}. "
            f"Proceeding to requirements analysis."
        )
    )

    timings = dict(state.get("stage_timings", {}))
    timings["intake"] = elapsed

    return {
        "current_stage": "requirements",
        "errors": errors,
        "messages": [system_msg, human_msg, ai_msg],
        "stage_timings": timings,
    }
