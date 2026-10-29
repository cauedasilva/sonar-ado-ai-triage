"""Montagem do título e do corpo HTML do work item.

Todo texto externo (Sonar e LLM) passa por html.escape: o corpo do work item
é HTML renderizado pelo Azure DevOps (RNF03).
"""

from __future__ import annotations

from html import escape

from .models import Recommendation, SonarIssue

MAX_TITLE = 255


def work_item_title(issue: SonarIssue) -> str:
    location = f"{issue.file_path}:{issue.line}" if issue.line else issue.file_path
    title = f"[Sonar][{issue.severity}] {issue.rule} em {location}"
    return title if len(title) <= MAX_TITLE else title[: MAX_TITLE - 3] + "..."


def dedupe_tag(issue: SonarIssue) -> str:
    return f"sonar-key:{issue.key}"


def work_item_html(issue: SonarIssue, rec: Recommendation, snippet: str) -> str:
    steps = "".join(f"<li>{escape(step)}</li>" for step in rec.passos_correcao)
    refs = ", ".join(escape(ref) for ref in rec.referencias) or "-"
    example = f"<h3>Exemplo de correção</h3><pre>{escape(rec.exemplo_codigo)}</pre>" if rec.exemplo_codigo else ""
    code = f"<h3>Trecho apontado</h3><pre>{escape(snippet)}</pre>" if snippet else ""

    return (
        f"<h2>{escape(issue.message)}</h2>"
        f"<p><b>Projeto:</b> {escape(issue.project)}<br>"
        f"<b>Arquivo:</b> {escape(issue.file_path)} (linha {escape(str(issue.line or '-'))})<br>"
        f"<b>Regra:</b> {escape(issue.rule)} | <b>Severidade:</b> {escape(issue.severity)}<br>"
        f'<b>Sonar:</b> <a href="{escape(issue.url, quote=True)}">abrir issue</a></p>'
        f"{code}"
        f"<h3>Resumo</h3><p>{escape(rec.resumo)}</p>"
        f"<h3>Risco</h3><p>{escape(rec.risco)}</p>"
        f"<h3>Como corrigir</h3><ol>{steps}</ol>"
        f"{example}"
        f"<p><b>Referências:</b> {refs}</p>"
        f"<p><i>Recomendação gerada por IA (confiança: {escape(rec.confianca)}). "
        f"Revise antes de aplicar.</i></p>"
    )


def preview_page(title: str, body: str, tags: list[str]) -> str:
    return (
        "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
        f"<title>{escape(title)}</title>"
        "<body style='font-family:system-ui;max-width:860px;margin:2rem auto;padding:0 1rem'>"
        f"<h1 style='font-size:1.2rem'>{escape(title)}</h1>"
        f"<p><b>Tags:</b> {escape('; '.join(tags))}</p><hr>{body}</body></html>"
    )
