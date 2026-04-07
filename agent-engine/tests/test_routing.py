"""
Tests for routing functions in edges/routing.py.

Each routing function is tested with approved, rejected, and escalate cases
using minimal SDLCState dicts.
"""

from __future__ import annotations

import pytest

from src.platform.state.sdlc_state import default_llm_usage
from src.platform.graphs.edges.routing import (
    route_after_requirements_approval,
    route_after_qa,
    route_after_staging_approval,
)


def _base_state(**overrides) -> dict:
    """Build a minimal SDLCState dict for routing tests."""
    base = dict(
        run_id="test-run",
        product_id="SelfCare-001",
        thread_id="test-run",
        jira_epic_id="SC-42",
        figma_url=None,
        prd_s3_url=None,
        requirements=None,
        architecture=None,
        code_artifacts=[],
        qa_results=None,
        deployment=None,
        current_stage="intake",
        qa_iteration=0,
        max_qa_iterations=3,
        approval_status=None,
        human_feedback=None,
        requirements_rejection_count=0,
        messages=[],
        llm_usage=default_llm_usage(),
        errors=[],
        stage_timings={},
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# route_after_requirements_approval
# ---------------------------------------------------------------------------


class TestRouteAfterRequirementsApproval:
    def test_approved(self):
        state = _base_state(approval_status="approved", requirements_rejection_count=0)
        assert route_after_requirements_approval(state) == "approved"

    def test_rejected_first_time(self):
        state = _base_state(approval_status="rejected", requirements_rejection_count=1)
        assert route_after_requirements_approval(state) == "rejected"

    def test_escalate_after_two_rejections(self):
        state = _base_state(approval_status="rejected", requirements_rejection_count=2)
        assert route_after_requirements_approval(state) == "escalate"

    def test_escalate_when_rejection_count_exceeds_max(self):
        state = _base_state(approval_status="rejected", requirements_rejection_count=5)
        assert route_after_requirements_approval(state) == "escalate"

    def test_approved_status_takes_priority_over_zero_rejections(self):
        state = _base_state(approval_status="approved", requirements_rejection_count=0)
        route = route_after_requirements_approval(state)
        assert route == "approved"

    def test_none_approval_status_defaults_to_approved(self):
        state = _base_state(approval_status=None, requirements_rejection_count=0)
        assert route_after_requirements_approval(state) == "approved"


# ---------------------------------------------------------------------------
# route_after_qa
# ---------------------------------------------------------------------------


class TestRouteAfterQA:
    def _passing_qa(self):
        return {
            "passed": True,
            "unit_test_results": {"total": 100, "passed": 100, "failed": 0},
            "integration_test_results": {},
            "security_scan_results": {"vulnerabilities_critical": 0},
            "code_review_findings": [],
            "e2e_test_results": {},
            "failure_summary": None,
        }

    def _failing_qa(self):
        return {
            "passed": False,
            "unit_test_results": {"total": 100, "passed": 80, "failed": 20},
            "integration_test_results": {},
            "security_scan_results": {"vulnerabilities_critical": 1},
            "code_review_findings": ["Critical: SQL injection"],
            "e2e_test_results": {},
            "failure_summary": "Unit tests failed",
        }

    def test_passed_when_qa_passes(self):
        state = _base_state(qa_results=self._passing_qa(), qa_iteration=1)
        assert route_after_qa(state) == "passed"

    def test_retry_when_qa_fails_and_iterations_remain(self):
        state = _base_state(
            qa_results=self._failing_qa(),
            qa_iteration=1,
            max_qa_iterations=3,
        )
        assert route_after_qa(state) == "retry"

    def test_retry_at_second_iteration(self):
        state = _base_state(
            qa_results=self._failing_qa(),
            qa_iteration=2,
            max_qa_iterations=3,
        )
        assert route_after_qa(state) == "retry"

    def test_escalate_when_max_iterations_reached(self):
        state = _base_state(
            qa_results=self._failing_qa(),
            qa_iteration=3,
            max_qa_iterations=3,
        )
        assert route_after_qa(state) == "escalate"

    def test_escalate_when_iterations_exceed_max(self):
        state = _base_state(
            qa_results=self._failing_qa(),
            qa_iteration=5,
            max_qa_iterations=3,
        )
        assert route_after_qa(state) == "escalate"

    def test_passed_takes_priority_over_iteration_count(self):
        state = _base_state(
            qa_results=self._passing_qa(),
            qa_iteration=3,
            max_qa_iterations=3,
        )
        assert route_after_qa(state) == "passed"


# ---------------------------------------------------------------------------
# route_after_staging_approval
# ---------------------------------------------------------------------------


class TestRouteAfterStagingApproval:
    def test_approved(self):
        state = _base_state(
            approval_status="approved",
            requirements_rejection_count=0,
        )
        assert route_after_staging_approval(state) == "approved"

    def test_rejected(self):
        state = _base_state(
            approval_status="rejected",
            requirements_rejection_count=0,
        )
        assert route_after_staging_approval(state) == "rejected"

    def test_escalate_after_max_rejections(self):
        state = _base_state(
            approval_status="rejected",
            requirements_rejection_count=2,
        )
        assert route_after_staging_approval(state) == "escalate"

    def test_none_approval_defaults_to_approved(self):
        state = _base_state(approval_status=None, requirements_rejection_count=0)
        assert route_after_staging_approval(state) == "approved"
