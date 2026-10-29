"""Testes dos critérios de aceite da SPEC 001 (sem rede, sem credenciais)."""

from __future__ import annotations

import json

import pytest

from triage.demo import DemoSource, demo_issues
from triage.llm import InvalidLLMResponse, OfflineProvider, Recommender, parse_recommendation
from triage.models import Recommendation, SonarIssue, Usage
from triage.pipeline import run
from triage.render import dedupe_tag, work_item_html, work_item_title
from triage.sonar import slice_lines

VALID = {
    "resumo": "SQL montado por concatenação.",
    "risco": "Leitura de dados de outros usuários.",
    "passos_correcao": ["Usar PreparedStatement."],
    "exemplo_codigo": "",
    "referencias": ["CWE-89"],
    "confianca": "alta",
}


class FakeSink:
    def __init__(self, existing_tags: set[str] | None = None) -> None:
        self.existing = existing_tags or set()
        self.created: list[tuple[str, str, list[str]]] = []

    def find_by_tag(self, tag: str) -> list[int]:
        return [1] if tag in self.existing else []

    def create(self, title: str, html: str, tags: list[str]) -> dict:
        self.created.append((title, html, tags))
        return {"id": 100 + len(self.created)}


class CountingProvider(OfflineProvider):
    def __init__(self, response: str | None = None) -> None:
        self.calls = 0
        self.response = response

    def complete(self, system: str, user: str):
        self.calls += 1
        if self.response is not None:
            return self.response, 10, 10
        return super().complete(system, user)


def _run(tmp_path, issues, provider, sink, apply=True):
    recommender = Recommender(provider, tmp_path / "cache", Usage())
    return run(issues, DemoSource(), recommender, sink=sink, apply=apply,
               output_dir=tmp_path / "out", extra_tags=["appsec"])


def test_criterio1_cria_work_item_com_titulo_tag_e_corpo(tmp_path):
    sink = FakeSink()
    report = _run(tmp_path, demo_issues()[:1], CountingProvider(), sink)

    assert len(report.created) == 1
    title, html, tags = sink.created[0]
    assert title == "[Sonar][BLOCKER] javasecurity:S3649 em src/main/java/com/example/UserRepository.java:9"
    assert "sonar-key:DEMO-0001" in tags
    assert "Como corrigir" in html


def test_criterio2_nao_duplica(tmp_path):
    issue = demo_issues()[0]
    sink = FakeSink({dedupe_tag(issue)})
    provider = CountingProvider()
    report = _run(tmp_path, [issue], provider, sink)

    assert report.skipped == [issue.key]
    assert sink.created == []
    assert provider.calls == 0  # nem gasta token com issue já tratada


def test_criterio3_resposta_invalida_vira_falha_e_lote_continua(tmp_path):
    issues = demo_issues()
    provider = CountingProvider(response="Claro! Aqui está a correção...")
    report = _run(tmp_path, issues, provider, FakeSink())

    assert len(report.failed) == len(issues)
    assert provider.calls == len(issues)


def test_criterio4_html_escapado():
    issue = demo_issues()[0]
    rec = Recommendation(**{**VALID, "resumo": "<script>alert(1)</script>"})
    html = work_item_html(issue, rec, "<img src=x onerror=alert(1)>")

    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "<img" not in html


def test_criterio5_cache_evita_segunda_chamada(tmp_path):
    issue = demo_issues()[0]
    twin = SonarIssue(**{**issue.__dict__, "key": "DEMO-0099"})
    provider = CountingProvider()
    report = _run(tmp_path, [issue, twin], provider, FakeSink())

    assert provider.calls == 1
    assert report.usage.cache_hits == 1
    assert len(report.created) == 2


def test_criterio6_demo_gera_previews(tmp_path):
    report = _run(tmp_path, demo_issues(), CountingProvider(), sink=None, apply=False)
    assert len(report.previewed) == 2
    assert not report.failed


@pytest.mark.parametrize("bad", [
    "[]",
    json.dumps({**VALID, "confianca": "certeza"}),
    json.dumps({**VALID, "passos_correcao": []}),
    json.dumps({k: v for k, v in VALID.items() if k != "risco"}),
])
def test_schema_rejeita(bad):
    with pytest.raises(InvalidLLMResponse):
        parse_recommendation(bad)


def test_schema_aceita_cerca_markdown():
    rec = parse_recommendation("```json\n" + json.dumps(VALID) + "\n```")
    assert rec.confianca == "alta"


def test_slice_lines_marca_linha():
    out = slice_lines("a\nb\nc\nd\ne", 3, 1)
    assert out.splitlines() == ["  2 | b", "> 3 | c", "  4 | d"]


def test_titulo_limitado():
    issue = SonarIssue(**{**demo_issues()[0].__dict__, "file_path": "x" * 400})
    assert len(work_item_title(issue)) == 255
