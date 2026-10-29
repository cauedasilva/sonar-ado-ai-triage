"""Configuração lida de variáveis de ambiente (nunca de código versionado)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def load_dotenv(path: Path = Path(".env")) -> None:
    """Carrega um .env simples sem sobrescrever o que já está no ambiente."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    sonar_url: str = ""
    sonar_token: str = ""
    sonar_severities: str = "BLOCKER,HIGH"
    sonar_statuses: str = "OPEN"
    sonar_projects: str = ""

    ado_org_url: str = ""          # ex.: https://dev.azure.com/minha-org
    ado_project: str = ""
    ado_token: str = ""
    ado_work_item_type: str = "Task"
    ado_area_path: str = ""
    ado_extra_tags: list[str] = field(default_factory=list)

    llm_provider: str = "anthropic"  # anthropic | offline
    llm_model: str = "claude-haiku-5-5"
    llm_max_output_tokens: int = 1200

    context_lines: int = 8
    max_snippet_chars: int = 3000
    max_rule_chars: int = 2500
    http_timeout: int = 30
    output_dir: Path = Path("output")
    cache_dir: Path = Path(".cache")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            sonar_url=_env("SONAR_URL").rstrip("/"),
            sonar_token=_env("SONAR_TOKEN"),
            sonar_severities=_env("SONAR_SEVERITIES", "BLOCKER,HIGH"),
            sonar_statuses=_env("SONAR_STATUSES", "OPEN"),
            sonar_projects=_env("SONAR_PROJECTS"),
            ado_org_url=_env("ADO_ORG_URL").rstrip("/"),
            ado_project=_env("ADO_PROJECT"),
            ado_token=_env("ADO_TOKEN"),
            ado_work_item_type=_env("ADO_WORK_ITEM_TYPE", "Task"),
            ado_area_path=_env("ADO_AREA_PATH"),
            ado_extra_tags=[t.strip() for t in _env("ADO_EXTRA_TAGS", "appsec;sonar").split(";") if t.strip()],
            llm_provider=_env("LLM_PROVIDER", "anthropic").lower(),
            llm_model=_env("LLM_MODEL", "claude-haiku-5-5"),
            llm_max_output_tokens=int(_env("LLM_MAX_OUTPUT_TOKENS", "1200")),
            context_lines=int(_env("CONTEXT_LINES", "8")),
        )

    def missing_for_run(self, apply: bool) -> list[str]:
        required = {"SONAR_URL": self.sonar_url, "SONAR_TOKEN": self.sonar_token}
        if apply:
            required |= {"ADO_ORG_URL": self.ado_org_url, "ADO_PROJECT": self.ado_project, "ADO_TOKEN": self.ado_token}
        if self.llm_provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
            required["ANTHROPIC_API_KEY"] = ""
        return [name for name, value in required.items() if not value]
