"""
GitHub integration tools.

Provides a real GitHubClient (GitHub REST API v3) and a MockGitHubClient
that returns canned data.  Use ``get_github_client()`` as the factory.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.parse
from typing import Any, Dict, List

from ..config import settings


class GitHubClient:
    """Thin GitHub REST API v3 client."""

    API_BASE = "https://api.github.com"

    def __init__(self, token: str) -> None:
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        }

    def _request(self, path: str, method: str = "GET", body: Any = None) -> Any:
        url = f"{self.API_BASE}/{path.lstrip('/')}"
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, headers=self._headers, method=method)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def get_branch(self, owner: str, repo: str, branch: str) -> Dict[str, Any]:
        data = self._request(f"repos/{owner}/{repo}/branches/{branch}")
        return {
            "name": data["name"],
            "commit_sha": data["commit"]["sha"],
            "protected": data.get("protected", False),
        }

    def create_branch(self, owner: str, repo: str, branch: str, from_sha: str) -> Dict[str, Any]:
        payload = {"ref": f"refs/heads/{branch}", "sha": from_sha}
        result = self._request(f"repos/{owner}/{repo}/git/refs", method="POST", body=payload)
        return {"branch": branch, "sha": result["object"]["sha"]}

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str = "",
    ) -> Dict[str, Any]:
        payload = {"title": title, "head": head, "base": base, "body": body}
        result = self._request(f"repos/{owner}/{repo}/pulls", method="POST", body=payload)
        return {
            "pr_number": result["number"],
            "pr_url": result["html_url"],
            "state": result["state"],
        }

    def get_commit(self, owner: str, repo: str, sha: str) -> Dict[str, Any]:
        data = self._request(f"repos/{owner}/{repo}/commits/{sha}")
        return {
            "sha": data["sha"],
            "message": data["commit"]["message"],
            "author": data["commit"]["author"]["name"],
        }

    def list_workflow_runs(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        data = self._request(f"repos/{owner}/{repo}/actions/runs")
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "status": r["status"],
                "conclusion": r.get("conclusion"),
                "url": r["html_url"],
            }
            for r in data.get("workflow_runs", [])[:5]
        ]


class MockGitHubClient:
    """Returns realistic canned GitHub data without API calls."""

    _FAKE_SHA = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    _FAKE_PR_URL = "https://github.com/myorg/selfcare-catalog/pull/42"
    _FAKE_PIPELINE_URL = (
        "https://github.com/myorg/selfcare-catalog/actions/runs/9876543210"
    )

    def get_branch(self, owner: str, repo: str, branch: str) -> Dict[str, Any]:
        return {"name": branch, "commit_sha": self._FAKE_SHA, "protected": branch == "main"}

    def create_branch(self, owner: str, repo: str, branch: str, from_sha: str) -> Dict[str, Any]:
        return {"branch": branch, "sha": self._FAKE_SHA}

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str = "",
    ) -> Dict[str, Any]:
        return {"pr_number": 42, "pr_url": self._FAKE_PR_URL, "state": "open"}

    def get_commit(self, owner: str, repo: str, sha: str) -> Dict[str, Any]:
        return {
            "sha": self._FAKE_SHA,
            "message": "feat: implement product catalog service",
            "author": "agent-bot",
        }

    def list_workflow_runs(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        return [
            {
                "id": 9876543210,
                "name": "CI/CD Pipeline",
                "status": "completed",
                "conclusion": "success",
                "url": self._FAKE_PIPELINE_URL,
            }
        ]


def get_github_client() -> GitHubClient | MockGitHubClient:
    """Factory — returns mock or real client based on MOCK_MODE."""
    if settings.mock_mode:
        return MockGitHubClient()
    return GitHubClient(token=settings.github_token)
