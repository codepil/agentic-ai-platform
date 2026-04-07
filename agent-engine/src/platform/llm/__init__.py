"""LLM model router — returns the right model for each task."""

from .model_router import get_llm

__all__ = ["get_llm"]
