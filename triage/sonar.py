"""Cliente mínimo da Web API do SonarQube."""

from __future__ import annotations

import logging
from typing import Any

import requests

from .config import Settings
from .models import SonarIssue

logger = logging.getLogger(__name__)


class SonarClient:
    def __init__(self, settings: Settings, session: requests.Session | None = None) -> None:
        self.base = settings.sonar_url
        self.timeout = settings.http_timeout
        self.settings = settings
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {settings.sonar_token}", "Accept": "application/json"})
        self._rule_cache: dict[str, str] = {}

    def _get(self, path: str, params: dict[str, Any]) -> requests.Response:
        resp = self.session.get(f"{self.base}{path}", params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp

    def search_issues(self, limit: int | None = None) -> list[SonarIssue]:
        params: dict[str, Any] = {
            "impactSoftwareQualities": "SECURITY",
            "impactSeverities": self.settings.sonar_severities,
            "issueStatuses": self.settings.sonar_statuses,
            "ps": 100,
            "p": 1,
        }
        if self.settings.sonar_projects:
            params["projects"] = self.settings.sonar_projects

        issues: list[SonarIssue] = []
        while True:
            payload = self._get("/api/issues/search", params).json()
            batch = payload.get("issues", [])
            issues.extend(SonarIssue.from_api(raw, self.base) for raw in batch)
            total = int(payload.get("paging", {}).get("total", len(issues)))
            if not batch or len(issues) >= total or (limit and len(issues) >= limit):
                break
            params["p"] += 1

        logger.info("Sonar: %d issue(s) encontrada(s)", len(issues))
        return issues[:limit] if limit else issues

    def rule_description(self, rule_key: str) -> str:
        """Descrição da regra em texto, com cache por execução (RF03)."""
        if rule_key not in self._rule_cache:
            rule = self._get("/api/rules/show", {"key": rule_key}).json().get("rule", {})
            sections = rule.get("descriptionSections") or []
            text = "\n\n".join(s.get("content", "") for s in sections) or rule.get("htmlDesc", "")
            self._rule_cache[rule_key] = f"{rule.get('name', rule_key)}\n\n{text}"
        return self._rule_cache[rule_key]

    def code_snippet(self, issue: SonarIssue, context: int) -> str:
        """Linhas ao redor da issue, numeradas (RF04)."""
        try:
            raw = self._get("/api/sources/raw", {"key": issue.component}).text
        except requests.HTTPError as exc:
            logger.warning("Sem acesso ao código de %s: %s", issue.component, exc)
            return ""
        return slice_lines(raw, issue.line, context)


def slice_lines(source: str, line: int | None, context: int) -> str:
    lines = source.splitlines()
    if not lines:
        return ""
    center = (line or 1) - 1
    start, end = max(0, center - context), min(len(lines), center + context + 1)
    width = len(str(end))
    return "\n".join(
        f"{'>' if i == center else ' '} {str(i + 1).rjust(width)} | {lines[i]}" for i in range(start, end)
    )
