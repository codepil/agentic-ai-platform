"""
Tests for individual graph nodes.

Nodes are async functions; we use asyncio.run() / pytest-asyncio to test them.
Crew calls are mocked using unittest.mock.patch so tests never hit real APIs.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.platform.state.sdlc_state import SDLCState, default_llm_usage, QAResults


def _base_state(**overrides) -> SDLCState:
    base = SDLCState(
        run_id="test-run-001",
        product_id="SelfCare-001",
        thread_id="test-run-001",
        jira_epic_id="SC-42",
        figma_url="https://www.figma.com/file/TEST1234/Test",
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
    base.update(overrides)  # type: ignore[attr-defined]
    return base


def run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# intake_node
# ---------------------------------------------------------------------------


class TestIntakeNode:
    def test_returns_correct_stage(self):
        from src.platform.graphs.nodes.intake import intake_node

        state = _base_state()
        result = run(intake_node(state))

        assert result["current_stage"] == "requirements"

    def test_appends_messages(self):
        from src.platform.graphs.nodes.intake import intake_node

        state = _base_state()
        result = run(intake_node(state))

        msgs = result.get("messages", [])
        assert len(msgs) >= 1
        # Should contain a SystemMessage, HumanMessage, and AIMessage
        types = {type(m).__name__ for m in msgs}
        assert "AIMessage" in types

    def test_records_stage_timing(self):
        from src.platform.graphs.nodes.intake import intake_node

        state = _base_state()
        result = run(intake_node(state))

        assert "intake" in result["stage_timings"]
        assert result["stage_timings"]["intake"] >= 0

    def test_no_errors_in_happy_path(self):
        from src.platform.graphs.nodes.intake import intake_node

        state = _base_state()
        result = run(intake_node(state))

        # In mock mode Jira and Figma should not fail
        assert result.get("errors") == [] or result.get("errors") is None

    def test_system_message_contains_product_id(self):
        from src.platform.graphs.nodes.intake import intake_node

        state = _base_state()
        result = run(intake_node(state))

        system_msgs = [m for m in result["messages"] if isinstance(m, SystemMessage)]
        assert any("SelfCare-001" in m.content for m in system_msgs)


# ---------------------------------------------------------------------------
# requirements_node
# ---------------------------------------------------------------------------


class TestRequirementsNode:
    def test_calls_requirements_crew_kickoff(self):
        from src.platform.graphs.nodes.requirements import requirements_node

        mock_output = {
            "user_stories": [{"id": "US-1", "title": "Test story"}],
            "acceptance_criteria": [{"story_id": "US-1"}],
            "sap_dependencies": ["BAPI_TEST"],
            "ambiguities": [],
            "jira_subtask_ids": ["SC-101"],
        }

        with patch(
            "src.platform.graphs.nodes.requirements.RequirementsCrew.kickoff",
            return_value=mock_output,
        ):
            state = _base_state()
            result = run(requirements_node(state))

        assert result["requirements"] == mock_output

    def test_updates_current_stage(self):
        from src.platform.graphs.nodes.requirements import requirements_node

        mock_output = {
            "user_stories": [],
            "acceptance_criteria": [],
            "sap_dependencies": [],
            "ambiguities": [],
            "jira_subtask_ids": [],
        }

        with patch(
            "src.platform.graphs.nodes.requirements.RequirementsCrew.kickoff",
            return_value=mock_output,
        ):
            state = _base_state()
            result = run(requirements_node(state))

        assert result["current_stage"] == "requirements_approval"

    def test_appends_ai_message(self):
        from src.platform.graphs.nodes.requirements import requirements_node

        mock_output = {
            "user_stories": [{"id": "US-1"}],
            "acceptance_criteria": [],
            "sap_dependencies": [],
            "ambiguities": [],
            "jira_subtask_ids": [],
        }

        with patch(
            "src.platform.graphs.nodes.requirements.RequirementsCrew.kickoff",
            return_value=mock_output,
        ):
            state = _base_state()
            result = run(requirements_node(state))

        msgs = result.get("messages", [])
        assert any(isinstance(m, AIMessage) for m in msgs)

    def test_resets_approval_status(self):
        from src.platform.graphs.nodes.requirements import requirements_node

        mock_output = {
            "user_stories": [],
            "acceptance_criteria": [],
            "sap_dependencies": [],
            "ambiguities": [],
            "jira_subtask_ids": [],
        }

        with patch(
            "src.platform.graphs.nodes.requirements.RequirementsCrew.kickoff",
            return_value=mock_output,
        ):
            state = _base_state(approval_status="rejected", human_feedback="Change story 1")
            result = run(requirements_node(state))

        assert result["approval_status"] is None
        assert result["human_feedback"] is None


# ---------------------------------------------------------------------------
# qa_failed_handler_node
# ---------------------------------------------------------------------------


class TestQAFailedHandlerNode:
    def _failing_qa(self) -> QAResults:
        return QAResults(
            passed=False,
            unit_test_results={
                "total": 100,
                "passed": 80,
                "failed": 20,
                "coverage_pct": 62.0,
            },
            integration_test_results={"total": 20, "passed": 18, "failed": 2},
            security_scan_results={
                "vulnerabilities_critical": 1,
                "vulnerabilities_high": 2,
            },
            code_review_findings=[
                "Critical: SQL injection in ProductRepository.java line 88"
            ],
            e2e_test_results={"total": 12, "passed": 9, "failed": 3},
            failure_summary="20 unit tests failed, 1 critical vulnerability",
        )

    def test_builds_failure_summary_in_human_feedback(self):
        from src.platform.graphs.nodes.qa_failed_handler import qa_failed_handler_node

        state = _base_state(qa_results=self._failing_qa(), qa_iteration=1)
        result = run(qa_failed_handler_node(state))

        feedback = result.get("human_feedback", "")
        assert "QA FAILURE REPORT" in feedback
        assert "20" in feedback  # 20 unit test failures

    def test_sets_current_stage_to_dev(self):
        from src.platform.graphs.nodes.qa_failed_handler import qa_failed_handler_node

        state = _base_state(qa_results=self._failing_qa(), qa_iteration=1)
        result = run(qa_failed_handler_node(state))

        assert result["current_stage"] == "dev"

    def test_mentions_critical_security_issues(self):
        from src.platform.graphs.nodes.qa_failed_handler import qa_failed_handler_node

        state = _base_state(qa_results=self._failing_qa(), qa_iteration=1)
        result = run(qa_failed_handler_node(state))

        feedback = result["human_feedback"]
        assert "critical" in feedback.lower()

    def test_mentions_code_review_findings(self):
        from src.platform.graphs.nodes.qa_failed_handler import qa_failed_handler_node

        state = _base_state(qa_results=self._failing_qa(), qa_iteration=2)
        result = run(qa_failed_handler_node(state))

        feedback = result["human_feedback"]
        assert "SQL injection" in feedback

    def test_appends_ai_message(self):
        from src.platform.graphs.nodes.qa_failed_handler import qa_failed_handler_node

        state = _base_state(qa_results=self._failing_qa(), qa_iteration=1)
        result = run(qa_failed_handler_node(state))

        msgs = result.get("messages", [])
        assert any(isinstance(m, AIMessage) for m in msgs)


# ---------------------------------------------------------------------------
# error_handler_node
# ---------------------------------------------------------------------------


class TestErrorHandlerNode:
    def test_sets_current_stage_escalated(self):
        from src.platform.graphs.nodes.error_handler import error_handler_node

        state = _base_state(
            qa_iteration=3,
            max_qa_iterations=3,
            requirements_rejection_count=0,
        )
        result = run(error_handler_node(state))

        assert result["current_stage"] == "escalated"

    def test_appends_error_to_errors_list(self):
        from src.platform.graphs.nodes.error_handler import error_handler_node

        state = _base_state(errors=["Something went wrong"])
        result = run(error_handler_node(state))

        assert len(result["errors"]) >= 2  # original + escalation msg

    def test_appends_ai_message(self):
        from src.platform.graphs.nodes.error_handler import error_handler_node

        state = _base_state(requirements_rejection_count=2)
        result = run(error_handler_node(state))

        msgs = result.get("messages", [])
        assert any(isinstance(m, AIMessage) for m in msgs)

    def test_escalation_reason_for_requirements_rejection(self):
        from src.platform.graphs.nodes.error_handler import error_handler_node

        state = _base_state(requirements_rejection_count=2)
        result = run(error_handler_node(state))

        # The error message should mention requirements rejection
        ai_msgs = [m for m in result["messages"] if isinstance(m, AIMessage)]
        assert any("rejected" in m.content.lower() for m in ai_msgs)

    def test_escalation_reason_for_qa_max_iterations(self):
        from src.platform.graphs.nodes.error_handler import error_handler_node

        failing_qa = QAResults(
            passed=False,
            unit_test_results={"total": 100, "passed": 80, "failed": 20},
            integration_test_results={},
            security_scan_results={"vulnerabilities_critical": 0},
            code_review_findings=[],
            e2e_test_results={},
            failure_summary="Tests failed",
        )
        state = _base_state(
            qa_results=failing_qa,
            qa_iteration=3,
            max_qa_iterations=3,
            requirements_rejection_count=0,
        )
        result = run(error_handler_node(state))

        ai_msgs = [m for m in result["messages"] if isinstance(m, AIMessage)]
        assert any("qa" in m.content.lower() or "iteration" in m.content.lower() for m in ai_msgs)
