"""
Pydantic output models for each CrewAI crew.

These models mirror the TypedDicts in ``sdlc_state.py`` but add Pydantic
validation.  ``model_config = ConfigDict(extra='allow')`` is set on every
model so extra fields from LLM output are accepted gracefully.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Requirements Crew
# ---------------------------------------------------------------------------


class UserStory(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    as_a: str
    i_want: str
    so_that: str
    story_points: int


class AcceptanceCriteria(BaseModel):
    model_config = ConfigDict(extra="allow")

    story_id: str
    given: str
    when: str
    then: str


class RequirementsCrewOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_stories: List[UserStory]
    acceptance_criteria: List[AcceptanceCriteria]
    sap_dependencies: List[str]
    ambiguities: List[str]
    jira_subtask_ids: List[str]


# ---------------------------------------------------------------------------
# Architecture Crew
# ---------------------------------------------------------------------------


class OpenAPIEndpoint(BaseModel):
    model_config = ConfigDict(extra="allow")

    method: str
    path: str
    summary: str
    query_params: Optional[List[str]] = None
    request_body: Optional[str] = None


class OpenAPISpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    service: str
    version: str
    base_path: str
    endpoints: List[OpenAPIEndpoint]


class ArchitectureCrewOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    openapi_specs: List[OpenAPISpec]
    mongodb_schemas: List[Dict[str, Any]]
    adr_ids: List[str]
    sap_integration_plan: Dict[str, Any]
    service_dependency_graph: Dict[str, Any]


# ---------------------------------------------------------------------------
# Dev Crew
# ---------------------------------------------------------------------------


class CodeArtifactModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    artifact_id: str
    type: str
    repo: str
    file_path: str
    git_branch: str
    git_commit_sha: str
    content_hash: str


class DevCrewOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    code_artifacts: List[CodeArtifactModel]


# ---------------------------------------------------------------------------
# QA Crew
# ---------------------------------------------------------------------------


class QACrewOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    passed: bool
    unit_test_results: Dict[str, Any]
    integration_test_results: Dict[str, Any]
    security_scan_results: Dict[str, Any]
    code_review_findings: List[str]
    e2e_test_results: Dict[str, Any]
    failure_summary: Optional[str] = None


# ---------------------------------------------------------------------------
# DevOps Crew
# ---------------------------------------------------------------------------


class DeploymentResultModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    environment: str
    service_urls: Dict[str, str]
    git_pr_url: str
    pipeline_run_url: str
    deployed_at: str


class DevOpsCrewOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    deployment: DeploymentResultModel
