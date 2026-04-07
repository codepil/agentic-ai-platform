"""
Tests for individual CrewAI crew implementations.

All tests run with MOCK_MODE=true (enforced by conftest.py) so no real
API calls or CrewAI agent initialisation occurs.
"""

from __future__ import annotations

import os

import pytest

# Ensure mock mode before any platform imports
os.environ["MOCK_MODE"] = "true"


# ---------------------------------------------------------------------------
# TestRequirementsCrew
# ---------------------------------------------------------------------------


class TestRequirementsCrew:
    def _crew(self):
        from src.platform.crews.requirements_crew import RequirementsCrew
        return RequirementsCrew()

    def test_mock_returns_correct_output_shape(self):
        result = self._crew().kickoff({})
        assert "user_stories" in result
        assert "acceptance_criteria" in result
        assert "sap_dependencies" in result
        assert "ambiguities" in result
        assert "jira_subtask_ids" in result

    def test_user_stories_have_required_fields(self):
        result = self._crew().kickoff({})
        for story in result["user_stories"]:
            assert "id" in story
            assert "title" in story
            assert "as_a" in story
            assert "i_want" in story
            assert "so_that" in story
            assert "story_points" in story
            assert isinstance(story["story_points"], int)

    def test_acceptance_criteria_reference_valid_story_ids(self):
        result = self._crew().kickoff({})
        story_ids = {s["id"] for s in result["user_stories"]}
        for criterion in result["acceptance_criteria"]:
            assert criterion["story_id"] in story_ids

    def test_sap_dependencies_are_strings(self):
        result = self._crew().kickoff({})
        assert isinstance(result["sap_dependencies"], list)
        for dep in result["sap_dependencies"]:
            assert isinstance(dep, str)
        assert len(result["sap_dependencies"]) > 0

    def test_jira_subtask_ids_are_strings(self):
        result = self._crew().kickoff({})
        assert isinstance(result["jira_subtask_ids"], list)
        for jid in result["jira_subtask_ids"]:
            assert isinstance(jid, str)
        assert len(result["jira_subtask_ids"]) > 0


# ---------------------------------------------------------------------------
# TestArchitectureCrew
# ---------------------------------------------------------------------------


class TestArchitectureCrew:
    def _crew(self):
        from src.platform.crews.architecture_crew import ArchitectureCrew
        return ArchitectureCrew()

    def test_mock_returns_correct_output_shape(self):
        result = self._crew().kickoff({})
        assert "openapi_specs" in result
        assert "mongodb_schemas" in result
        assert "adr_ids" in result
        assert "sap_integration_plan" in result
        assert "service_dependency_graph" in result

    def test_openapi_specs_have_service_and_endpoints(self):
        result = self._crew().kickoff({})
        assert len(result["openapi_specs"]) > 0
        for spec in result["openapi_specs"]:
            assert "service" in spec
            assert "endpoints" in spec
            assert isinstance(spec["endpoints"], list)
            assert len(spec["endpoints"]) > 0
            for ep in spec["endpoints"]:
                assert "method" in ep
                assert "path" in ep

    def test_mongodb_schemas_have_collection_and_schema(self):
        result = self._crew().kickoff({})
        assert len(result["mongodb_schemas"]) > 0
        for schema_doc in result["mongodb_schemas"]:
            assert "collection" in schema_doc
            assert "schema" in schema_doc

    def test_sap_integration_plan_has_endpoints(self):
        result = self._crew().kickoff({})
        plan = result["sap_integration_plan"]
        assert "endpoints" in plan
        assert isinstance(plan["endpoints"], list)
        assert len(plan["endpoints"]) > 0

    def test_adr_ids_are_not_empty(self):
        result = self._crew().kickoff({})
        assert isinstance(result["adr_ids"], list)
        assert len(result["adr_ids"]) > 0
        for adr_id in result["adr_ids"]:
            assert isinstance(adr_id, str)


# ---------------------------------------------------------------------------
# TestDevCrew
# ---------------------------------------------------------------------------


class TestDevCrew:
    def _crew(self):
        from src.platform.crews.dev_crew import DevCrew
        return DevCrew()

    def test_mock_returns_code_artifacts_list(self):
        result = self._crew().kickoff({})
        assert "code_artifacts" in result
        assert isinstance(result["code_artifacts"], list)
        assert len(result["code_artifacts"]) > 0

    def test_artifacts_have_all_required_fields(self):
        result = self._crew().kickoff({})
        required = {"artifact_id", "type", "repo", "file_path", "git_branch", "git_commit_sha", "content_hash"}
        for artifact in result["code_artifacts"]:
            for field in required:
                assert field in artifact, f"Missing field '{field}' in artifact {artifact}"
                assert isinstance(artifact[field], str)
                assert artifact[field] != ""

    def test_artifacts_include_java_service(self):
        result = self._crew().kickoff({})
        types = [a["type"] for a in result["code_artifacts"]]
        assert "java_service" in types

    def test_artifacts_include_react_component(self):
        result = self._crew().kickoff({})
        types = [a["type"] for a in result["code_artifacts"]]
        assert "react_component" in types

    def test_artifacts_include_test_suite(self):
        result = self._crew().kickoff({})
        types = [a["type"] for a in result["code_artifacts"]]
        assert "test_suite" in types


# ---------------------------------------------------------------------------
# TestQACrew
# ---------------------------------------------------------------------------


class TestQACrew:
    def _crew(self):
        from src.platform.crews.qa_crew import QACrew
        return QACrew()

    def test_mock_pass_mode(self):
        result = self._crew().kickoff({})
        assert result["passed"] is True

    def test_mock_fail_mode_via_force_fail(self):
        result = self._crew().kickoff({"force_fail": True})
        assert result["passed"] is False

    def test_pass_result_has_no_failure_summary(self):
        result = self._crew().kickoff({})
        assert result["failure_summary"] is None

    def test_fail_result_has_failure_summary(self):
        result = self._crew().kickoff({"force_fail": True})
        assert result["failure_summary"] is not None
        assert isinstance(result["failure_summary"], str)
        assert len(result["failure_summary"]) > 0

    def test_security_scan_present_in_both_modes(self):
        pass_result = self._crew().kickoff({})
        fail_result = self._crew().kickoff({"force_fail": True})
        for result in [pass_result, fail_result]:
            assert "security_scan_results" in result
            scan = result["security_scan_results"]
            assert "vulnerabilities_critical" in scan
            assert "vulnerabilities_high" in scan
            assert "scanner" in scan


# ---------------------------------------------------------------------------
# TestDevOpsCrew
# ---------------------------------------------------------------------------


class TestDevOpsCrew:
    def _crew(self):
        from src.platform.crews.devops_crew import DevOpsCrew
        return DevOpsCrew()

    def test_mock_returns_deployment_dict(self):
        result = self._crew().kickoff({})
        assert "deployment" in result
        dep = result["deployment"]
        assert "environment" in dep
        assert "service_urls" in dep
        assert "git_pr_url" in dep
        assert "pipeline_run_url" in dep
        assert "deployed_at" in dep

    def test_staging_deployment_has_staging_url(self):
        result = self._crew().kickoff({"environment": "staging"})
        dep = result["deployment"]
        assert dep["environment"] == "staging"
        urls = dep["service_urls"]
        # At least one URL should reference staging
        all_urls = " ".join(urls.values())
        assert "staging" in all_urls

    def test_deployment_has_pr_url_and_pipeline_url(self):
        result = self._crew().kickoff({})
        dep = result["deployment"]
        assert dep["git_pr_url"].startswith("https://")
        assert dep["pipeline_run_url"].startswith("https://")

    def test_deployed_at_is_iso_format(self):
        from datetime import datetime
        result = self._crew().kickoff({})
        dep = result["deployment"]
        deployed_at = dep["deployed_at"]
        # Should be parseable as ISO-8601
        dt = datetime.fromisoformat(deployed_at)
        assert dt is not None


# ---------------------------------------------------------------------------
# TestOutputModels
# ---------------------------------------------------------------------------


class TestOutputModels:
    def test_requirements_output_model_validates(self):
        from src.platform.crews.output_models import RequirementsCrewOutput
        data = {
            "user_stories": [
                {
                    "id": "US-001",
                    "title": "Browse catalog",
                    "as_a": "customer",
                    "i_want": "to browse",
                    "so_that": "I can buy",
                    "story_points": 5,
                }
            ],
            "acceptance_criteria": [
                {
                    "story_id": "US-001",
                    "given": "I am on the catalog page",
                    "when": "I apply a filter",
                    "then": "results are filtered",
                }
            ],
            "sap_dependencies": ["BAPI_MATERIAL_GET_ALL"],
            "ambiguities": ["Guest checkout scope unclear"],
            "jira_subtask_ids": ["SC-101"],
        }
        model = RequirementsCrewOutput(**data)
        assert len(model.user_stories) == 1
        assert model.user_stories[0].id == "US-001"
        assert len(model.acceptance_criteria) == 1

    def test_architecture_output_model_validates(self):
        from src.platform.crews.output_models import ArchitectureCrewOutput
        data = {
            "openapi_specs": [
                {
                    "service": "product-catalog",
                    "version": "1.0.0",
                    "base_path": "/api/v1/products",
                    "endpoints": [
                        {"method": "GET", "path": "/", "summary": "List products"}
                    ],
                }
            ],
            "mongodb_schemas": [
                {
                    "collection": "products",
                    "schema": {"bsonType": "object"},
                    "indexes": [],
                }
            ],
            "adr_ids": ["ADR-001"],
            "sap_integration_plan": {"type": "OData", "endpoints": []},
            "service_dependency_graph": {"nodes": [], "edges": []},
        }
        model = ArchitectureCrewOutput(**data)
        assert len(model.openapi_specs) == 1
        assert model.openapi_specs[0].service == "product-catalog"

    def test_dev_crew_output_model_validates(self):
        from src.platform.crews.output_models import DevCrewOutput
        data = {
            "code_artifacts": [
                {
                    "artifact_id": "artifact-001",
                    "type": "java_service",
                    "repo": "myorg/selfcare-catalog",
                    "file_path": "src/main/java/ProductController.java",
                    "git_branch": "feature/SC-101",
                    "git_commit_sha": "abc123",
                    "content_hash": "sha256:abc",
                }
            ]
        }
        model = DevCrewOutput(**data)
        assert len(model.code_artifacts) == 1
        assert model.code_artifacts[0].type == "java_service"

    def test_qa_crew_output_model_validates_pass(self):
        from src.platform.crews.output_models import QACrewOutput
        data = {
            "passed": True,
            "unit_test_results": {"total": 100, "passed": 100, "failed": 0, "coverage_pct": 90.0},
            "integration_test_results": {"total": 20, "passed": 20, "failed": 0},
            "security_scan_results": {"vulnerabilities_critical": 0, "scanner": "Snyk"},
            "code_review_findings": [],
            "e2e_test_results": {"total": 10, "passed": 10, "failed": 0},
            "failure_summary": None,
        }
        model = QACrewOutput(**data)
        assert model.passed is True
        assert model.failure_summary is None

    def test_qa_crew_output_model_validates_fail(self):
        from src.platform.crews.output_models import QACrewOutput
        data = {
            "passed": False,
            "unit_test_results": {"total": 100, "passed": 60, "failed": 40, "coverage_pct": 60.0},
            "integration_test_results": {"total": 20, "passed": 15, "failed": 5},
            "security_scan_results": {"vulnerabilities_critical": 1, "scanner": "Snyk"},
            "code_review_findings": ["Critical: SQL injection found"],
            "e2e_test_results": {"total": 10, "passed": 7, "failed": 3},
            "failure_summary": "40 unit tests failed. 1 critical CVE.",
        }
        model = QACrewOutput(**data)
        assert model.passed is False
        assert "CVE" in model.failure_summary

    def test_devops_crew_output_model_validates(self):
        from src.platform.crews.output_models import DevOpsCrewOutput
        from datetime import datetime, timezone
        data = {
            "deployment": {
                "environment": "staging",
                "service_urls": {
                    "product-catalog-service": "https://catalog.staging.example.com"
                },
                "git_pr_url": "https://github.com/myorg/repo/pull/42",
                "pipeline_run_url": "https://github.com/myorg/repo/actions/runs/123",
                "deployed_at": datetime.now(timezone.utc).isoformat(),
            }
        }
        model = DevOpsCrewOutput(**data)
        assert model.deployment.environment == "staging"
        assert "product-catalog-service" in model.deployment.service_urls
