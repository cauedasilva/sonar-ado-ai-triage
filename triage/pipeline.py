"""Orquestração: Sonar → LLM → (pré-visualização | Azure DevOps)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable, Iterable, Protocol

from .llm import InvalidLLMResponse, Recommender, build_user_prompt
from .models import RunReport, SonarIssue
from .render import dedupe_tag, preview_page, work_item_html, work_item_title

logger = logging.getLogger(__name__)


class IssueSource(Protocol):
    def rule_description(self, rule_key: str) -> str: ...
    def code_snippet(self, issue: SonarIssue, context: int) -> str: ...


class WorkItemSink(Protocol):
    def find_by_tag(self, tag: str) -> list[int]: ...
    def create(self, title: str, html: str, tags: list[str]) -> dict: ...


def _safe_filename(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text)[:80]


def run(
    issues: Iterable[SonarIssue],
    source: IssueSource,
    recommender: Recommender,
    *,
    sink: WorkItemSink | None,
    apply: bool,
    output_dir: Path,
    extra_tags: list[str],
    context_lines: int = 8,
    max_rule_chars: int = 2500,
    max_snippet_chars: int = 3000,
    report: RunReport | None = None,
    on_progress: Callable[[str], None] = logger.info,
) -> RunReport:
    report = report or RunReport(usage=recommender.usage)
    output_dir.mkdir(parents=True, exist_ok=True)

    for issue in issues:
        tag = dedupe_tag(issue)
        try:
            if sink is not None and sink.find_by_tag(tag):
                report.skipped.append(issue.key)
                on_progress(f"pulada (já existe work item): {issue.key}")
                continue

            snippet = source.code_snippet(issue, context_lines)
            rule_text = source.rule_description(issue.rule)
            prompt = build_user_prompt(issue, rule_text, snippet, max_rule_chars, max_snippet_chars)
            rec = recommender.recommend(f"{issue.rule}\n{snippet}", prompt)

            title = work_item_title(issue)
            html = work_item_html(issue, rec, snippet)
            tags = [tag, *extra_tags]

            if apply and sink is not None:
                created = sink.create(title, html, tags)
                report.created.append(f"{issue.key} -> #{created.get('id')}")
                on_progress(f"criada #{created.get('id')}: {title}")
            else:
                path = output_dir / f"{_safe_filename(issue.key)}.html"
                path.write_text(preview_page(title, html, tags), encoding="utf-8")
                report.previewed.append(str(path))
                on_progress(f"simulação: {path}")

        except InvalidLLMResponse as exc:
            report.failed.append((issue.key, f"resposta do LLM inválida: {exc}"))
            logger.warning("Issue %s: resposta do LLM inválida: %s", issue.key, exc)
        except Exception as exc:  # uma issue com erro não derruba o lote (RNF06)
            report.failed.append((issue.key, str(exc)))
            logger.exception("Issue %s: falha", issue.key)

    return report


def summary(report: RunReport) -> str:
    u = report.usage
    lines = [
        f"Criadas:      {len(report.created)}",
        f"Simuladas:    {len(report.previewed)}",
        f"Puladas:      {len(report.skipped)}",
        f"Falhas:       {len(report.failed)}",
        f"Chamadas LLM: {u.llm_calls} (cache evitou {u.cache_hits})",
        f"Tokens:       {u.input_tokens} entrada / {u.output_tokens} saída",
    ]
    lines += [f"  - {key}: {reason}" for key, reason in report.failed]
    return "\n".join(lines)
