"""
Abstract base class for all SDLC crews.

Each concrete crew must implement ``kickoff(inputs)`` which runs the
CrewAI multi-agent workflow and returns a dict matching the relevant
TypedDict (RequirementsOutput, ArchitectureOutput, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from ..config import settings
from ..state.sdlc_state import LLMUsage


class BaseCrew(ABC):
    """Abstract base class for platform crews."""

    @property
    def mock_mode(self) -> bool:
        """True when MOCK_MODE env var is set."""
        return settings.mock_mode

    @abstractmethod
    def kickoff(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the crew workflow with *inputs* and return structured output.

        In mock mode implementors should return hardcoded but realistic data
        without instantiating any real CrewAI objects.
        """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _accumulate_usage(existing: LLMUsage, new_tokens: Dict[str, Any]) -> LLMUsage:
        """
        Merge *new_tokens* into *existing* LLMUsage and return the updated dict.

        Parameters
        ----------
        existing:
            The current accumulated LLMUsage dict.
        new_tokens:
            A dict with optional keys ``input_tokens``, ``output_tokens``,
            ``cost_usd`` (any missing key is treated as 0).
        """
        return LLMUsage(
            input_tokens=existing["input_tokens"] + int(new_tokens.get("input_tokens", 0)),
            output_tokens=existing["output_tokens"] + int(new_tokens.get("output_tokens", 0)),
            cost_usd=existing["cost_usd"] + float(new_tokens.get("cost_usd", 0.0)),
        )
