"""
Platform configuration loaded from environment variables.
Exposes a singleton `settings` object used throughout the platform.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Platform settings loaded from environment variables."""

    def __init__(self) -> None:
        self.anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
        self.mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.mongo_db_name: str = os.getenv("MONGO_DB_NAME", "agent_platform")

        self.jira_url: str = os.getenv("JIRA_URL", "https://yourorg.atlassian.net")
        self.jira_user: str = os.getenv("JIRA_USER", "")
        self.jira_token: str = os.getenv("JIRA_TOKEN", "")

        self.github_token: str = os.getenv("GITHUB_TOKEN", "")

        self.figma_token: str = os.getenv("FIGMA_TOKEN", "")

        # MOCK_MODE disables real API calls — used in tests and local dev
        _mock_raw = os.getenv("MOCK_MODE", "false")
        self.mock_mode: bool = _mock_raw.lower() in ("1", "true", "yes")

        # LLM model identifiers
        self.sonnet_model: str = os.getenv(
            "SONNET_MODEL", "claude-sonnet-4-5"
        )
        self.haiku_model: str = os.getenv(
            "HAIKU_MODEL", "claude-haiku-4-5"
        )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"Settings(mock_mode={self.mock_mode}, "
            f"mongo_db_name={self.mongo_db_name!r})"
        )


# Singleton
settings = Settings()
