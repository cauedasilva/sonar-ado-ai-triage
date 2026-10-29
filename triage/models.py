"""Estruturas de dados compartilhadas entre as etapas do fluxo."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SonarIssue:
    key: str
    project: str
    component: str
    file_path: str
    line: int | None
    rule: str
    message: str
    severity: str
    url: str

    @classmethod
    def from_api(cls, raw: dict[str, Any], sonar_url: str) -> "SonarIssue":
        project = str(raw.get("project", ""))
        component = str(raw.get("component", ""))
        prefix = f"{project}:"
        impacts = raw.get("impacts") or [{}]
        severity = str(impacts[0].get("severity") or raw.get("severity") or "UNKNOWN").upper()
        key = str(raw.get("key", ""))
        return cls(
            key=key,
            project=project,
            component=component,
            file_path=component[len(prefix):] if component.startswith(prefix) else component,
            line=raw.get("line"),
            rule=str(raw.get("rule", "")),
            message=str(raw.get("message", "")),
            severity=severity,
            url=f"{sonar_url}/project/issues?id={project}&open={key}",
        )


@dataclass
class Recommendation:
    resumo: str
    risco: str
    passos_correcao: list[str]
    exemplo_codigo: str
    referencias: list[str]
    confianca: str  # alta | media | baixa


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0
    cache_hits: int = 0

    def add(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.llm_calls += 1


@dataclass
class RunReport:
    created: list[str] = field(default_factory=list)
    previewed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
