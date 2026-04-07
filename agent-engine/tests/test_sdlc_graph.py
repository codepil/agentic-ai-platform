"""
End-to-end tests for the complete SDLC LangGraph workflow.

These tests exercise the full graph from intake to production deployment
(or escalation) using MemorySaver and MOCK_MODE=true.

Human-in-the-loop interrupts are simulated by resuming with Command(resume=...).
All nodes are async, so we use the async graph API (astream / ainvoke) and
run everything with asyncio.run().
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import patch

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from src.platform.state.sdlc_state import SDLCState, default_llm_usage, QAResults
from src.platform.graphs.sdlc_graph import build_sdlc_graph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(
    run_id: str | None = None,
    product_id: str = "SelfCare-001",
    max_qa_iterations: int = 3,
) -> SDLCState:
    rid = run_id or f"test-{uuid.uuid4().hex[:8]}"
    return SDLCState(
        run_id=rid,
        product_id=product_id,
        thread_id=rid,
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
        max_qa_iterations=max_qa_iterations,
        approval_status=None,
        human_feedback=None,
        requirements_rejection_count=0,
        messages=[],
        llm_usage=default_llm_usage(),
        errors=[],
        stage_timings={},
    )


def _graph_and_config():
    """Create a fresh graph + config dict for each test."""
    checkpointer = MemorySaver()
    graph = build_sdlc_graph(checkpointer)
    state = _make_state()
    config = {"configurable": {"thread_id": state["thread_id"]}}
    return graph, state, config


async def _run_until_interrupt_async(graph, state_or_cmd, config):
    """
    Async-stream the graph until it either ends or hits an interrupt.
    Returns the final streamed event dict.
    """
    last = None
    async for event in graph.astream(state_or_cmd, config=config, stream_mode="values"):
        last = event
    return last


def _run_until_interrupt(graph, state_or_cmd, config):
    """Synchronous wrapper around the async stream helper."""
    return asyncio.run(_run_until_interrupt_async(graph, state_or_cmd, config))


def _get_next_nodes(graph, config):
    snapshot = graph.get_state(config)
    return list(snapshot.next)


# ---------------------------------------------------------------------------
# Test: Full happy path — both interrupts auto-approved
# ---------------------------------------------------------------------------


class TestFullSDLCRunApproved:
    def test_full_sdlc_run_approved(self):
        """
        Full end-to-end:
        intake → requirements → INTERRUPT (requirements_approval)
        → resume approved → architecture → dev → qa → devops
        → INTERRUPT (staging_approval)
        → resume approved → deploy_prod → END
        """
        graph, initial_state, config = _graph_and_config()

        # Phase 1: run until requirements_approval interrupt
        _run_until_interrupt(graph, initial_state, config)

        next_nodes = _get_next_nodes(graph, config)
        assert "requirements_approval" in next_nodes, (
            f"Expected interrupt at requirements_approval, got {next_nodes}"
        )

        # Resume with approval
        _run_until_interrupt(
            graph,
            Command(resume={"decision": "approved", "feedback": None}),
            config,
        )

        next_nodes = _get_next_nodes(graph, config)
        assert "staging_approval" in next_nodes, (
            f"Expected interrupt at staging_approval, got {next_nodes}"
        )

        # Resume staging approval
        _run_until_interrupt(
            graph,
            Command(resume={"decision": "approved", "feedback": None}),
            config,
        )

        # Graph should be done
        next_nodes = _get_next_nodes(graph, config)
        assert next_nodes == [], f"Expected graph to be finished, but next={next_nodes}"

        final = graph.get_state(config).values
        assert final["current_stage"] == "deployed_production"
        assert final["deployment"]["environment"] == "production"

    def test_final_state_has_all_artefacts(self):
        """Verify all SDLC artefacts are populated in the final state."""
        graph, initial_state, config = _graph_and_config()

        _run_until_interrupt(graph, initial_state, config)
        _run_until_interrupt(
            graph, Command(resume={"decision": "approved", "feedback": None}), config
        )
        _run_until_interrupt(
            graph, Command(resume={"decision": "approved", "feedback": None}), config
        )

        final = graph.get_state(config).values

        assert final["requirements"] is not None
        assert final["architecture"] is not None
        assert len(final["code_artifacts"]) > 0
        assert final["qa_results"] is not None
        assert final["qa_results"]["passed"] is True
        assert final["deployment"] is not None

    def test_messages_accumulate_throughout_run(self):
        """Messages from all nodes should be present in the final state."""
        graph, initial_state, config = _graph_and_config()

        _run_until_interrupt(graph, initial_state, config)
        _run_until_interrupt(
            graph, Command(resume={"decision": "approved", "feedback": None}), config
        )
        _run_until_interrupt(
            graph, Command(resume={"decision": "approved", "feedback": None}), config
        )

        final = graph.get_state(config).values
        # Should have messages from: intake, requirements, requirements_approval,
        # architecture, dev, qa, devops, staging_approval, deploy_prod
        assert len(final["messages"]) >= 6


# ---------------------------------------------------------------------------
# Test: QA retry then pass
# ---------------------------------------------------------------------------


class TestQARetryThenPass:
    def test_qa_retry_then_pass(self):
        """
        QA fails on iteration 1, passes on iteration 2.
        Assert qa_iteration is incremented correctly and final state passes.
        """
        graph, initial_state, config = _graph_and_config()

        # We control QACrew.kickoff to fail first, then pass
        call_count = [0]
        original_kickoff = None

        def mock_kickoff(self_crew, inputs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First QA run — fail
                return {
                    "passed": False,
                    "unit_test_results": {"total": 100, "passed": 80, "failed": 20, "coverage_pct": 62.0},
                    "integration_test_results": {"total": 10, "passed": 10, "failed": 0},
                    "security_scan_results": {"vulnerabilities_critical": 0, "vulnerabilities_high": 0},
                    "code_review_findings": ["Minor: magic number on line 42"],
                    "e2e_test_results": {"total": 5, "passed": 5, "failed": 0},
                    "failure_summary": "20 unit tests failed (coverage 62% < 80%)",
                }
            else:
                # Second QA run — pass
                return {
                    "passed": True,
                    "unit_test_results": {"total": 100, "passed": 100, "failed": 0, "coverage_pct": 87.0},
                    "integration_test_results": {"total": 10, "passed": 10, "failed": 0},
                    "security_scan_results": {"vulnerabilities_critical": 0, "vulnerabilities_high": 0},
                    "code_review_findings": [],
                    "e2e_test_results": {"total": 5, "passed": 5, "failed": 0},
                    "failure_summary": None,
                }

        with patch(
            "src.platform.graphs.nodes.qa.QACrew.kickoff",
            mock_kickoff,
        ):
            _run_until_interrupt(graph, initial_state, config)
            _run_until_interrupt(
                graph, Command(resume={"decision": "approved", "feedback": None}), config
            )
            _run_until_interrupt(
                graph, Command(resume={"decision": "approved", "feedback": None}), config
            )

        final = graph.get_state(config).values
        assert final["qa_results"]["passed"] is True
        assert final["qa_iteration"] == 2
        assert final["current_stage"] == "deployed_production"


# ---------------------------------------------------------------------------
# Test: Requirements rejection then approval
# ---------------------------------------------------------------------------


class TestRequirementsRejectionThenApproval:
    def test_requirements_rejection_then_approval(self):
        """
        Reject requirements once, then approve.
        Verify state updated with human feedback and requirements were regenerated.
        """
        graph, initial_state, config = _graph_and_config()

        # Phase 1: run to first interrupt
        _run_until_interrupt(graph, initial_state, config)

        # Check we're at requirements_approval
        snapshot = graph.get_state(config)
        assert "requirements_approval" in snapshot.next

        # Reject with feedback
        _run_until_interrupt(
            graph,
            Command(resume={
                "decision": "rejected",
                "feedback": "Please add story for bulk product upload",
            }),
            config,
        )

        # We should be back at requirements_approval after regeneration
        snapshot = graph.get_state(config)
        assert "requirements_approval" in snapshot.next

        # Check rejection count was tracked
        state_values = snapshot.values
        assert state_values["requirements_rejection_count"] >= 1

        # Now approve
        _run_until_interrupt(
            graph,
            Command(resume={"decision": "approved", "feedback": None}),
            config,
        )
        _run_until_interrupt(
            graph,
            Command(resume={"decision": "approved", "feedback": None}),
            config,
        )

        final = graph.get_state(config).values
        assert final["current_stage"] == "deployed_production"


# ---------------------------------------------------------------------------
# Test: QA max iterations escalates
# ---------------------------------------------------------------------------


class TestQAMaxIterationsEscalates:
    def test_qa_max_iterations_escalates(self):
        """
        QA always fails. After max_qa_iterations the graph should escalate.
        """
        graph, initial_state, config = _graph_and_config()
        initial_state = _make_state(
            run_id=initial_state["run_id"],
            max_qa_iterations=2,
        )
        config = {"configurable": {"thread_id": initial_state["thread_id"]}}

        def always_fail_kickoff(self_crew, inputs):
            return {
                "passed": False,
                "unit_test_results": {"total": 100, "passed": 70, "failed": 30, "coverage_pct": 55.0},
                "integration_test_results": {"total": 10, "passed": 8, "failed": 2},
                "security_scan_results": {"vulnerabilities_critical": 2, "vulnerabilities_high": 5},
                "code_review_findings": ["Critical: Remote code execution on line 77"],
                "e2e_test_results": {"total": 5, "passed": 2, "failed": 3},
                "failure_summary": "Critical security vulnerabilities and test failures",
            }

        with patch(
            "src.platform.graphs.nodes.qa.QACrew.kickoff",
            always_fail_kickoff,
        ):
            _run_until_interrupt(graph, initial_state, config)
            _run_until_interrupt(
                graph, Command(resume={"decision": "approved", "feedback": None}), config
            )
            # Graph should reach error_handler after max iterations
            # No more interrupts expected
            next_nodes = _get_next_nodes(graph, config)
            assert next_nodes == [], f"Expected graph to be done, got next={next_nodes}"

        final = graph.get_state(config).values
        assert final["current_stage"] == "escalated"
        assert len(final["errors"]) > 0

    def test_escalated_state_has_error_messages(self):
        """Ensure error_handler populates errors list with escalation context."""
        graph, initial_state, config = _graph_and_config()
        initial_state = _make_state(
            run_id=initial_state["run_id"],
            max_qa_iterations=1,
        )
        config = {"configurable": {"thread_id": initial_state["thread_id"]}}

        def always_fail_kickoff(self_crew, inputs):
            return {
                "passed": False,
                "unit_test_results": {"total": 10, "passed": 5, "failed": 5, "coverage_pct": 40.0},
                "integration_test_results": {},
                "security_scan_results": {"vulnerabilities_critical": 1},
                "code_review_findings": [],
                "e2e_test_results": {},
                "failure_summary": "Persistent failures",
            }

        with patch(
            "src.platform.graphs.nodes.qa.QACrew.kickoff",
            always_fail_kickoff,
        ):
            _run_until_interrupt(graph, initial_state, config)
            _run_until_interrupt(
                graph, Command(resume={"decision": "approved", "feedback": None}), config
            )

        final = graph.get_state(config).values
        assert final["current_stage"] == "escalated"
        # errors list should contain the escalation message
        errors_text = " ".join(final["errors"])
        assert "ESCALATION" in errors_text or len(final["errors"]) > 0
