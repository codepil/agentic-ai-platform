"""
LLM model router.

Returns the appropriate LangChain chat model for a given task name.
When MOCK_MODE is enabled, returns a FakeListChatModel so that no real
API calls are made during tests or local development.

Routing table
-------------
Haiku tasks  : parse_jira, summarise_qa, generate_cicd_yaml,
               generate_terraform, summarise_failure
Everything else → Claude Sonnet 4.5
"""

from __future__ import annotations

from typing import Union

from langchain_core.language_models.chat_models import BaseChatModel

from ..config import settings

# Tasks that should use the cheaper / faster Haiku model
_HAIKU_TASKS = frozenset(
    {
        "parse_jira",
        "summarise_qa",
        "generate_cicd_yaml",
        "generate_terraform",
        "summarise_failure",
    }
)

# Canned responses used by the FakeListChatModel in mock mode
_MOCK_RESPONSES = [
    "Mock LLM response for testing purposes.",
] * 1000  # large pool so it never runs out


def get_llm(task_name: str) -> BaseChatModel:
    """
    Return a chat model appropriate for *task_name*.

    Parameters
    ----------
    task_name:
        Logical name of the task (e.g. ``"parse_jira"``, ``"write_code"``).

    Returns
    -------
    BaseChatModel
        A ``FakeListChatModel`` when ``MOCK_MODE=true``, otherwise a real
        ``ChatAnthropic`` instance pointed at Haiku or Sonnet.
    """
    if settings.mock_mode:
        from langchain_core.language_models.fake_chat_models import FakeListChatModel

        return FakeListChatModel(responses=_MOCK_RESPONSES)

    from langchain_anthropic import ChatAnthropic

    model_id = (
        settings.haiku_model if task_name in _HAIKU_TASKS else settings.sonnet_model
    )
    return ChatAnthropic(
        model=model_id,
        api_key=settings.anthropic_api_key,
        temperature=0,
        max_tokens=4096,
    )
