"""Cliente mínimo da REST API de work items do Azure DevOps."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import requests
from requests.auth import HTTPBasicAuth

from .config import Settings

logger = logging.getLogger(__name__)

API_VERSION = "7.1"


class AzureDevOpsClient:
    def __init__(self, settings: Settings, session: requests.Session | None = None) -> None:
        self.settings = settings
        self.base = f"{settings.ado_org_url}/{quote(settings.ado_project, safe='')}/_apis/wit"
        self.timeout = settings.http_timeout
        self.session = session or requests.Session()
        self.session.auth = HTTPBasicAuth("", settings.ado_token)

    def find_by_tag(self, tag: str) -> list[int]:
        """IDs de work items com a tag de idempotência (RF07)."""
        safe_tag = tag.replace("'", "''")  # escape de aspas na WIQL
        query = (
            "SELECT [System.Id] FROM WorkItems "
            "WHERE [System.TeamProject] = @project "
            f"AND [System.Tags] CONTAINS '{safe_tag}'"
        )
        resp = self.session.post(
            f"{self.base}/wiql",
            params={"api-version": API_VERSION},
            json={"query": query},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return [int(item["id"]) for item in resp.json().get("workItems", [])]

    def create(self, title: str, html: str, tags: list[str]) -> dict[str, Any]:
        ops = [
            {"op": "add", "path": "/fields/System.Title", "value": title},
            {"op": "add", "path": "/fields/System.Description", "value": html},
            {"op": "add", "path": "/fields/System.Tags", "value": "; ".join(tags)},
        ]
        if self.settings.ado_area_path:
            ops.append({"op": "add", "path": "/fields/System.AreaPath", "value": self.settings.ado_area_path})

        work_item_type = quote(self.settings.ado_work_item_type, safe="")
        resp = self.session.post(
            f"{self.base}/workitems/${work_item_type}",
            params={"api-version": API_VERSION},
            json=ops,
            headers={"Content-Type": "application/json-patch+json"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()
