"""
Tests for state definitions in sdlc_state.py.

Covers:
- SDLCState can be instantiated with required fields
- add_messages annotation correctly accumulates messages
- LLMUsage default values
- Nested TypedDicts have expected shapes
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.platform.state.sdlc_state import (
    LLMUsage,
    RequirementsOutput,
    ArchitectureOutput,
    CodeArtifact,
    QAResults,
    DeploymentResult,
    SDLCState,
    default_llm_usage,
)


class TestLLMUsage:
    def test_default_values(self):
        usage = default_llm_usage()
        assert usage["input_tokens"] == 0
        assert usage["output_tokens"] == 0
        assert usage["cost_usd"] == 0.0

    def test_can_construct_with_values(self):
        usage = LLMUsage(input_tokens=1000, output_tokens=500, cost_usd=0.015)
        assert usage["input_tokens"] == 1000
        assert usage["output_tokens"] == 500
        assert usage["cost_usd"] == 0.015


class TestRequirementsOutput:
    def test_structure(self):
        req = RequirementsOutput(
            user_stories=[{"id": "US-1", "title": "Browse catalog"}],
            acceptance_criteria=[{"story_id": "US-1", "given": "...", "when": "...", "then": "..."}],
            sap_dependencies=["BAPI_MATERIAL_GET_ALL"],
            ambiguities=["Guest checkout scope unclear"],
            jira_subtask_ids=["SC-101"],
        )
        assert len(req["user_stories"]) == 1
        assert len(req["sap_dependencies"]) == 1
        assert req["jira_subtask_ids"] == ["SC-101"]


class TestArchitectureOutput:
    def test_structure(self):
        arch = ArchitectureOutput(
            openapi_specs=[{"service": "product-catalog", "version": "1.0.0"}],
            mongodb_schemas=[{"collection": "products"}],
            adr_ids=["ADR-001"],
            sap_integration_plan={"type": "OData v4"},
            service_dependency_graph={"nodes": ["svc-a", "svc-b"], "edges": []},
        )
        assert arch["adr_ids"] == ["ADR-001"]
        assert arch["sap_integration_plan"]["type"] == "OData v4"


class TestCodeArtifact:
    def test_structure(self):
        artifact = CodeArtifact(
            artifact_id="artifact-001",
            type="java_service",
            repo="myorg/selfcare-catalog",
            file_path="src/main/java/ProductController.java",
            git_branch="feature/SC-101",
            git_commit_sha="abc123def456",
            content_hash="sha256:deadbeef",
        )
        assert artifact["type"] == "java_service"
        assert artifact["git_branch"] == "feature/SC-101"


class TestQAResults:
    def test_passing_results(self):
        qa = QAResults(
            passed=True,
            unit_test_results={"total": 100, "passed": 100, "failed": 0},
            integration_test_results={"total": 20, "passed": 20, "failed": 0},
            security_scan_results={"vulnerabilities_critical": 0},
            code_review_findings=[],
            e2e_test_results={"total": 10, "passed": 10, "failed": 0},
            failure_summary=None,
        )
        assert qa["passed"] is True
        assert qa["failure_summary"] is None

    def test_failing_results(self):
        qa = QAResults(
            passed=False,
            unit_test_results={"total": 100, "passed": 80, "failed": 20},
            integration_test_results={"total": 20, "passed": 18, "failed": 2},
            security_scan_results={"vulnerabilities_critical": 1},
            code_review_findings=["Critical: SQL injection risk"],
            e2e_test_results={"total": 10, "passed": 7, "failed": 3},
            failure_summary="20 unit tests failed, 1 critical vulnerability",
        )
        assert qa["passed"] is False
        assert "SQL injection" in qa["code_review_findings"][0]
        assert qa["failure_summary"] is not None


class TestDeploymentResult:
    def test_structure(self):
        dep = DeploymentResult(
            environment="staging",
            service_urls={"product-catalog": "https://staging.example.com"},
            git_pr_url="https://github.com/org/repo/pull/42",
            pipeline_run_url="https://github.com/org/repo/actions/runs/123",
            deployed_at="2025-09-15T12:00:00+00:00",
        )
        assert dep["environment"] == "staging"
        assert "product-catalog" in dep["service_urls"]


class TestSDLCState:
    def test_can_instantiate_with_required_fields(self):
        state = SDLCState(
            run_id="run-001",
            product_id="SelfCare-001",
            thread_id="run-001",
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
        assert state["run_id"] == "run-001"
        assert state["product_id"] == "SelfCare-001"
        assert state["qa_iteration"] == 0
        assert state["max_qa_iterations"] == 3
        assert state["requirements_rejection_count"] == 0

    def test_messages_field_is_list(self):
        state = SDLCState(
            run_id="r1",
            product_id="p1",
            thread_id="r1",
            jira_epic_id="SC-1",
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
            messages=[HumanMessage(content="hello"), AIMessage(content="world")],
            llm_usage=default_llm_usage(),
            errors=[],
            stage_timings={},
        )
        assert len(state["messages"]) == 2
        assert state["messages"][0].content == "hello"
        assert state["messages"][1].content == "world"

    def test_add_messages_annotation_accumulates(self):
        """
        Verify the add_messages reducer behaviour by simulating what LangGraph
        does when merging partial state updates.
        """
        from langgraph.graph.message import add_messages

        existing = [HumanMessage(content="first")]
        new = [AIMessage(content="second")]
        result = add_messages(existing, new)

        assert len(result) == 2
        assert result[0].content == "first"
        assert result[1].content == "second"

    def test_stage_timings_is_dict(self):
        from src.platform.state.sdlc_state import default_llm_usage

        state = SDLCState(
            run_id="r2",
            product_id="p2",
            thread_id="r2",
            jira_epic_id="SC-2",
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
            stage_timings={"intake": 0.12},
        )
        assert state["stage_timings"]["intake"] == 0.12
