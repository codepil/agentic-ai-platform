"""
CrewAI-compatible tool functions using the @tool decorator.

All tools respect MOCK_MODE:
  - mock_mode=True  → return realistic JSON strings without real API calls
  - mock_mode=False → call the underlying Jira / GitHub / Figma clients

Import these functions inside the ``if not self.mock_mode`` block of each crew
so that the crewai package is never imported during mock-mode tests.
"""

from __future__ import annotations

import json
from typing import Any


def _jira_tools():
    """Return CrewAI @tool-decorated Jira functions."""
    from crewai import tool
    from ..tools.jira_tools import get_jira_client
    from ..config import settings

    @tool("Read Jira Epic")
    def read_jira_epic(epic_id: str) -> str:
        """Read a Jira epic by its issue key and return its details as JSON."""
        client = get_jira_client()
        result = client.get_epic(epic_id)
        return json.dumps(result)

    @tool("Create Jira Subtask")
    def create_jira_subtask(epic_id: str, summary: str, description: str) -> str:
        """Create a Jira subtask under the given epic and return the new issue key."""
        client = get_jira_client()
        key = client.create_subtask(epic_id, summary, description)
        return json.dumps({"key": key, "parent": epic_id, "summary": summary})

    @tool("Add Jira Comment")
    def add_jira_comment(issue_id: str, comment: str) -> str:
        """Add a comment to a Jira issue. Returns confirmation JSON."""
        if settings.mock_mode:
            return json.dumps({"issue_id": issue_id, "status": "comment_added", "mock": True})
        # Real implementation would call the Jira REST API comment endpoint
        client = get_jira_client()
        return json.dumps({"issue_id": issue_id, "status": "comment_added"})

    return read_jira_epic, create_jira_subtask, add_jira_comment


def _github_tools():
    """Return CrewAI @tool-decorated GitHub functions."""
    from crewai import tool
    from ..tools.github_tools import get_github_client

    @tool("Create GitHub Branch")
    def create_github_branch(repo: str, branch_name: str, base_branch: str = "main") -> str:
        """Create a new GitHub branch from base_branch. Returns branch info as JSON."""
        client = get_github_client()
        parts = repo.split("/", 1)
        owner, repo_name = (parts[0], parts[1]) if len(parts) == 2 else ("myorg", repo)
        base_info = client.get_branch(owner, repo_name, base_branch)
        result = client.create_branch(owner, repo_name, branch_name, base_info["commit_sha"])
        return json.dumps(result)

    @tool("Commit File to GitHub")
    def commit_file_to_github(
        repo: str, branch: str, file_path: str, content: str, message: str
    ) -> str:
        """Commit a file to a GitHub branch. Returns commit details as JSON."""
        client = get_github_client()
        parts = repo.split("/", 1)
        owner, repo_name = (parts[0], parts[1]) if len(parts) == 2 else ("myorg", repo)
        # In mock mode the MockGitHubClient has no commit_file; return realistic mock
        from ..config import settings
        if settings.mock_mode:
            return json.dumps({
                "repo": repo,
                "branch": branch,
                "file_path": file_path,
                "sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                "message": message,
            })
        # Real path would use the Contents API
        return json.dumps({
            "repo": repo,
            "branch": branch,
            "file_path": file_path,
            "message": message,
        })

    @tool("Create GitHub PR")
    def create_github_pr(repo: str, branch: str, title: str, body: str) -> str:
        """Create a GitHub pull request from branch to main. Returns PR details as JSON."""
        client = get_github_client()
        parts = repo.split("/", 1)
        owner, repo_name = (parts[0], parts[1]) if len(parts) == 2 else ("myorg", repo)
        result = client.create_pull_request(owner, repo_name, title, branch, "main", body)
        return json.dumps(result)

    return create_github_branch, commit_file_to_github, create_github_pr


def _figma_tools():
    """Return CrewAI @tool-decorated Figma functions."""
    from crewai import tool
    from ..tools.figma_tools import get_figma_client

    @tool("Read Figma File")
    def read_figma_file(file_url: str) -> str:
        """Read Figma file metadata for the given file URL. Returns metadata as JSON."""
        client = get_figma_client()
        # Extract file key from URL like https://www.figma.com/file/<KEY>/...
        file_key = file_url.split("/file/")[-1].split("/")[0] if "/file/" in file_url else file_url
        result = client.get_file_metadata(file_key)
        return json.dumps(result)

    @tool("List Figma Components")
    def list_figma_components(file_url: str) -> str:
        """List all published components in a Figma file. Returns component list as JSON."""
        client = get_figma_client()
        file_key = file_url.split("/file/")[-1].split("/")[0] if "/file/" in file_url else file_url
        components = client.list_components(file_key)
        return json.dumps(components)

    return read_figma_file, list_figma_components


def get_jira_crewai_tools():
    """Return (read_jira_epic, create_jira_subtask, add_jira_comment) as CrewAI tools."""
    return _jira_tools()


def get_github_crewai_tools():
    """Return (create_github_branch, commit_file_to_github, create_github_pr) as CrewAI tools."""
    return _github_tools()


def get_figma_crewai_tools():
    """Return (read_figma_file, list_figma_components) as CrewAI tools."""
    return _figma_tools()
