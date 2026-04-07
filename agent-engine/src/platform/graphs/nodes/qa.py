"""
QA node — runs the QACrew to validate all code artefacts.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from langchain_core.messages import AIMessage

from ...state.sdlc_state import SDLCState
from ...crews.qa_crew import QACrew


async def qa_node(state: SDLCState) -> Dict[str, Any]:
    """Run the QA crew and update state with test results."""
    t0 = time.time()

    crew = QACrew()
    result = crew.kickoff(
        inputs={
            "run_id": state["run_id"],
            "product_id": state["product_id"],
            "code_artifacts": state.get("code_artifacts", []),
            "architecture": state.get("architecture", {}),
            # Allow tests to inject force_fail via human_feedback metadata
            "force_fail": state.get("human_feedback", "").startswith("__force_fail__")
            if state.get("human_feedback")
            else False,
        }
    )

    qa_iteration = state.get("qa_iteration", 0) + 1
    elapsed = time.time() - t0
    timings = dict(state.get("stage_timings", {}))
    timings[f"qa_iteration_{qa_iteration}"] = elapsed

    passed = result.get("passed", False)
    msg = AIMessage(
        content=(
            f"QA iteration {qa_iteration} complete in {elapsed:.2f}s. "
            f"Passed: {passed}. "
            f"Unit: {result.get('unit_test_results', {}).get('passed', '?')}/"
            f"{result.get('unit_test_results', {}).get('total', '?')} tests. "
            f"Security: {result.get('security_scan_results', {}).get('vulnerabilities_critical', '?')} critical vulns. "
            f"E2E: {result.get('e2e_test_results', {}).get('passed', '?')}/"
            f"{result.get('e2e_test_results', {}).get('total', '?')} tests."
        )
    )

    return {
        "qa_results": result,
        "qa_iteration": qa_iteration,
        "current_stage": "qa",
        "messages": [msg],
        "stage_timings": timings,
    }
