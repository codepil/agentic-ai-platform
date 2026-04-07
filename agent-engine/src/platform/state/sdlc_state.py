"""
SDLC workflow state definitions using TypedDict.

All TypedDicts are used as LangGraph state schemas.  The SDLCState TypedDict
is the single source of truth for the full workflow run.
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# Sub-state TypedDicts
# ---------------------------------------------------------------------------


class LLMUsage(TypedDict):
    """Accumulated token usage and estimated cost for a workflow run."""

    input_tokens: int
    output_tokens: int
    cost_usd: float


class RequirementsOutput(TypedDict):
    """Structured output produced by the requirements crew."""

    user_stories: List[Dict[str, Any]]
    acceptance_criteria: List[Dict[str, Any]]
    sap_dependencies: List[str]
    ambiguities: List[str]
    jira_subtask_ids: List[str]


class ArchitectureOutput(TypedDict):
    """Structured output produced by the architecture crew."""

    openapi_specs: List[Dict[str, Any]]
    mongodb_schemas: List[Dict[str, Any]]
    adr_ids: List[str]
    sap_integration_plan: Dict[str, Any]
    service_dependency_graph: Dict[str, Any]


class CodeArtifact(TypedDict):
    """A single code artefact produced by the dev crew."""

    artifact_id: str
    type: str          # e.g. "java_service", "react_component", "test_suite"
    repo: str
    file_path: str
    git_branch: str
    git_commit_sha: str
    content_hash: str


class QAResults(TypedDict):
    """Results produced by the QA crew."""

    passed: bool
    unit_test_results: Dict[str, Any]
    integration_test_results: Dict[str, Any]
    security_scan_results: Dict[str, Any]
    code_review_findings: List[str]
    e2e_test_results: Dict[str, Any]
    failure_summary: Optional[str]


class DeploymentResult(TypedDict):
    """Output of a DevOps / deployment crew run."""

    environment: str                  # "staging" | "production"
    service_urls: Dict[str, str]
    git_pr_url: str
    pipeline_run_url: str
    deployed_at: str                  # ISO-8601 timestamp


# ---------------------------------------------------------------------------
# Top-level SDLC state
# ---------------------------------------------------------------------------


class SDLCState(TypedDict):
    """
    Complete mutable state for a single SDLC workflow run.

    LangGraph merges partial dicts returned by nodes, so nodes only need to
    return the keys they modify.  The `messages` field uses the `add_messages`
    reducer so messages are appended rather than replaced.
    """

    # --- Identity ---
    run_id: str
    product_id: str
    thread_id: str
    jira_epic_id: str
    figma_url: Optional[str]
    prd_s3_url: Optional[str]

    # --- SDLC artefacts ---
    requirements: Optional[RequirementsOutput]
    architecture: Optional[ArchitectureOutput]
    code_artifacts: List[CodeArtifact]
    qa_results: Optional[QAResults]
    deployment: Optional[DeploymentResult]

    # --- Workflow control ---
    current_stage: str          # e.g. "intake", "requirements", "deployed_production"
    qa_iteration: int
    max_qa_iterations: int
    approval_status: Optional[str]          # "approved" | "rejected" | None
    human_feedback: Optional[str]
    requirements_rejection_count: int       # tracks consecutive rejections

    # --- Conversation / audit ---
    messages: Annotated[List[BaseMessage], add_messages]

    # --- Observability ---
    llm_usage: LLMUsage
    errors: List[str]
    stage_timings: Dict[str, float]         # stage_name → elapsed seconds


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def default_llm_usage() -> LLMUsage:
    """Return a zeroed-out LLMUsage dict."""
    return LLMUsage(input_tokens=0, output_tokens=0, cost_usd=0.0)
