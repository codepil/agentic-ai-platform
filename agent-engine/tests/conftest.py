"""
Shared pytest fixtures for the SDLC platform test suite.

All tests run with MOCK_MODE=true so no real API keys are required.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict

import pytest

# Force mock mode for the entire test session before any platform imports
os.environ["MOCK_MODE"] = "true"
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

from langgraph.checkpoint.memory import MemorySaver

from src.platform.state.sdlc_state import SDLCState, default_llm_usage
from src.platform.graphs.sdlc_graph import build_sdlc_graph


# ---------------------------------------------------------------------------
# Settings fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    """Ensure MOCK_MODE is true for every test."""
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    # Re-initialise the settings singleton so the env var takes effect
    from src.platform import config as cfg_module
    cfg_module.settings.mock_mode = True
    yield


# ---------------------------------------------------------------------------
# Graph fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def memory_graph():
    """Return a compiled SDLC graph backed by MemorySaver."""
    checkpointer = MemorySaver()
    return build_sdlc_graph(checkpointer)


# ---------------------------------------------------------------------------
# State fixtures
# ---------------------------------------------------------------------------


def make_initial_state(
    run_id: str | None = None,
    product_id: str = "SelfCare-001",
    jira_epic_id: str = "SC-42",
) -> SDLCState:
    """Build a minimal valid SDLCState for tests."""
    rid = run_id or f"test-run-{uuid.uuid4().hex[:8]}"
    return SDLCState(
        run_id=rid,
        product_id=product_id,
        thread_id=rid,
        jira_epic_id=jira_epic_id,
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


@pytest.fixture
def initial_state() -> SDLCState:
    """Return a valid SDLCState for SelfCare-001."""
    return make_initial_state()


@pytest.fixture
def thread_config():
    """
    Return a factory that creates a LangGraph config dict for a given run_id.

    Usage::

        def test_foo(thread_config):
            config = thread_config("my-run-id")
            graph.invoke(state, config=config)
    """
    def _factory(run_id: str) -> Dict[str, Any]:
        return {"configurable": {"thread_id": run_id}}

    return _factory
