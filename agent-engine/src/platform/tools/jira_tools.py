"""
Jira integration tools.

Provides a real JiraClient that calls the Jira REST API and a MockJiraClient
that returns realistic canned data.  Use ``get_jira_client()`` to obtain the
correct implementation based on the MOCK_MODE setting.
"""

from __future__ import annotations

import urllib.request
import urllib.error
import base64
import json
from typing import Any, Dict, List

from ..config import settings


class JiraClient:
    """Thin Jira REST API v3 client."""

    def __init__(self, base_url: str, user: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        credentials = base64.b64encode(f"{user}:{token}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(self, path: str, method: str = "GET", body: Any = None) -> Any:
        url = f"{self._base_url}/rest/api/3/{path}"
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, headers=self._headers, method=method)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def get_epic(self, epic_id: str) -> Dict[str, Any]:
        """Fetch an epic by its issue key (e.g. ``PRJ-42``)."""
        issue = self._request(f"issue/{epic_id}")
        return {
            "id": issue["id"],
            "key": issue["key"],
            "summary": issue["fields"]["summary"],
            "description": issue["fields"].get("description", ""),
            "story_points": issue["fields"].get("story_points", 0),
            "status": issue["fields"]["status"]["name"],
        }

    def create_subtask(self, parent_key: str, summary: str, description: str) -> str:
        """Create a subtask under *parent_key* and return the new issue key."""
        payload = {
            "fields": {
                "project": {"key": parent_key.split("-")[0]},
                "parent": {"key": parent_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": description}]}
                    ],
                },
                "issuetype": {"name": "Subtask"},
            }
        }
        result = self._request("issue", method="POST", body=payload)
        return result["key"]

    def list_subtasks(self, epic_key: str) -> List[Dict[str, Any]]:
        """Return all subtasks linked to an epic."""
        jql = f'"Epic Link" = {epic_key} OR parent = {epic_key}'
        result = self._request(f"search?jql={urllib.parse.quote(jql)}&fields=summary,status")
        return [
            {
                "key": i["key"],
                "summary": i["fields"]["summary"],
                "status": i["fields"]["status"]["name"],
            }
            for i in result.get("issues", [])
        ]


class MockJiraClient:
    """Returns realistic canned Jira data without hitting any real API."""

    def get_epic(self, epic_id: str) -> Dict[str, Any]:
        return {
            "id": "10042",
            "key": epic_id,
            "summary": "Self-Care Product Catalog Modernisation",
            "description": (
                "Migrate the legacy product catalog to a cloud-native microservice "
                "backed by MongoDB Atlas, expose REST APIs consumed by the React SPA, "
                "and integrate with SAP for pricing and availability."
            ),
            "story_points": 89,
            "status": "In Progress",
        }

    def create_subtask(self, parent_key: str, summary: str, description: str) -> str:
        import uuid
        suffix = uuid.uuid4().hex[:4].upper()
        prefix = parent_key.split("-")[0]
        return f"{prefix}-{suffix}"

    def list_subtasks(self, epic_key: str) -> List[Dict[str, Any]]:
        return [
            {"key": f"{epic_key.split('-')[0]}-101", "summary": "Design API contract", "status": "To Do"},
            {"key": f"{epic_key.split('-')[0]}-102", "summary": "Implement product service", "status": "To Do"},
        ]


def get_jira_client() -> JiraClient | MockJiraClient:
    """Factory — returns mock or real client based on MOCK_MODE."""
    if settings.mock_mode:
        return MockJiraClient()
    return JiraClient(
        base_url=settings.jira_url,
        user=settings.jira_user,
        token=settings.jira_token,
    )
