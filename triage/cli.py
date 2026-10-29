"""Linha de comando.

  python -m triage --demo                 # fluxo completo com dados fictícios, sem rede
  python -m triage --limit 5              # simulação com dados reais (gera HTML em output/)
  python -m triage --limit 5 --apply      # cria os work items no Azure DevOps
"""

from __future__ import annotations

import argparse
import logging
import sys

from .azure_devops import AzureDevOpsClient
from .config import Settings, load_dotenv
from .demo import DemoSource, demo_issues
from .llm import Recommender, build_provider
from .models import Usage
from .pipeline import run, summary
from .sonar import SonarClient


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="triage", description="Sonar → LLM → Azure DevOps")
    parser.add_argument("--demo", action="store_true", help="usa dados fictícios e LLM offline")
    parser.add_argument("--apply", action="store_true", help="cria os work items (padrão: só simulação)")
    parser.add_argument("--limit", type=int, default=10, help="máximo de issues nesta execução (padrão 10)")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    load_dotenv()
    settings = Settings.from_env()
    usage = Usage()

    if args.demo:
        if args.apply:
            print("--demo não cria work items; ignorando --apply.", file=sys.stderr)
        recommender = Recommender(build_provider("offline", "", 0), settings.cache_dir / "demo", usage)
        report = run(
            demo_issues(), DemoSource(), recommender,
            sink=None, apply=False, output_dir=settings.output_dir / "demo",
            extra_tags=settings.ado_extra_tags, context_lines=settings.context_lines,
        )
        print(summary(report))
        return 0

    missing = settings.missing_for_run(args.apply)
    if missing:
        print(f"Configuração faltando: {', '.join(missing)} (veja .env.example)", file=sys.stderr)
        return 2

    provider = build_provider(settings.llm_provider, settings.llm_model, settings.llm_max_output_tokens)
    recommender = Recommender(provider, settings.cache_dir, usage)
    sonar = SonarClient(settings)
    # Mesmo em simulação, o Azure DevOps é consultado (se configurado) para mostrar o que seria pulado.
    sink = AzureDevOpsClient(settings) if settings.ado_token and settings.ado_org_url else None

    report = run(
        sonar.search_issues(limit=args.limit), sonar, recommender,
        sink=sink, apply=args.apply, output_dir=settings.output_dir,
        extra_tags=settings.ado_extra_tags, context_lines=settings.context_lines,
        max_rule_chars=settings.max_rule_chars, max_snippet_chars=settings.max_snippet_chars,
    )
    print(summary(report))
    return 1 if report.failed else 0
