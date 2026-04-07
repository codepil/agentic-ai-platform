"""
QA failed handler node — builds a structured failure summary for the dev crew.

This node does NOT call any crew. It reads the current QA results, extracts
actionable failure information, and stores it in ``human_feedback`` so the
dev crew (on its next iteration) knows what to fix.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from langchain_core.messages import AIMessage

from ...state.sdlc_state import SDLCState


async def qa_failed_handler_node(state: SDLCState) -> Dict[str, Any]:
    """Synthesise QA failure details into actionable feedback for the dev crew."""
    t0 = time.time()

    qa = state.get("qa_results") or {}
    iteration = state.get("qa_iteration", 0)
    max_iter = state.get("max_qa_iterations", 3)

    lines: list[str] = [
        f"QA FAILURE REPORT (iteration {iteration}/{max_iter})",
        "=" * 60,
    ]

    # Unit tests
    unit = qa.get("unit_test_results", {})
    if unit.get("failed", 0):
        lines.append(
            f"Unit tests: {unit['failed']} failures "
            f"(coverage {unit.get('coverage_pct', '?')}% — threshold 80%)"
        )

    # Integration tests
    integ = qa.get("integration_test_results", {})
    if integ.get("failed", 0):
        lines.append(f"Integration tests: {integ['failed']} failures")

    # Security
    sec = qa.get("security_scan_results", {})
    crit = sec.get("vulnerabilities_critical", 0)
    high = sec.get("vulnerabilities_high", 0)
    if crit or high:
        lines.append(f"Security: {crit} critical, {high} high vulnerabilities — must fix before merge")

    # Code review findings
    findings = qa.get("code_review_findings", [])
    if findings:
        lines.append("Code review findings:")
        for finding in findings:
            lines.append(f"  - {finding}")

    # E2E
    e2e = qa.get("e2e_test_results", {})
    if e2e.get("failed", 0):
        lines.append(f"E2E tests: {e2e['failed']} failures")

    # Overall summary if provided
    if qa.get("failure_summary"):
        lines.append(f"\nSummary: {qa['failure_summary']}")

    failure_feedback = "\n".join(lines)

    elapsed = time.time() - t0
    timings = dict(state.get("stage_timings", {}))
    timings["qa_failed_handler"] = elapsed

    msg = AIMessage(
        content=(
            f"QA failure analysis complete. "
            f"Sending failure report to dev crew for iteration {iteration + 1}. "
            f"Issues: unit={unit.get('failed', 0)} failures, "
            f"security={crit} critical vulns, "
            f"e2e={e2e.get('failed', 0)} failures."
        )
    )

    return {
        "human_feedback": failure_feedback,
        "current_stage": "dev",
        "messages": [msg],
        "stage_timings": timings,
    }
