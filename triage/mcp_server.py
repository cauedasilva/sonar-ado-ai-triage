"""Servidor MCP (Model Context Protocol): expõe o fluxo como ferramentas para agentes de IA.

Com ele, um agente como o Claude Code ou o Claude Desktop pode listar as issues,
pedir a recomendação de uma delas e, com confirmação humana, abrir o work item.

  pip install "mcp>=2"
  python -m triage.mcp_server

Exemplo de configuração no cliente MCP:
  {"mcpServers": {"sonar-triage": {"command": "python", "args": ["-m", "triage.mcp_server"]}}}
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .azure_devops import AzureDevOpsClient
from .config import Settings, load_dotenv
from .llm import Recommender, build_provider, build_user_prompt
from .models import Usage
from .render import dedupe_tag, work_item_html, work_item_title
from .sonar import SonarClient

load_dotenv()
settings = Settings.from_env()
sonar = SonarClient(settings)
recommender = Recommender(
    build_provider(settings.llm_provider, settings.llm_model, settings.llm_max_output_tokens),
    settings.cache_dir,
    Usage(),
)

mcp = MCPServer("sonar-triage")


def _find(issue_key: str):
    for issue in sonar.search_issues(limit=500):
        if issue.key == issue_key:
            return issue
    raise ValueError(f"Issue não encontrada entre as abertas: {issue_key}")


@mcp.tool()
def listar_issues(limite: int = 20) -> list[dict]:
    """Lista issues de segurança abertas no SonarQube (chave, projeto, regra, severidade, arquivo)."""
    return [
        {"key": i.key, "projeto": i.project, "regra": i.rule, "severidade": i.severity,
         "arquivo": f"{i.file_path}:{i.line}", "mensagem": i.message}
        for i in sonar.search_issues(limit=limite)
    ]


@mcp.tool()
def recomendar_correcao(issue_key: str) -> dict:
    """Gera a recomendação de correção (JSON validado) para uma issue do SonarQube."""
    issue = _find(issue_key)
    snippet = sonar.code_snippet(issue, settings.context_lines)
    prompt = build_user_prompt(issue, sonar.rule_description(issue.rule), snippet,
                               settings.max_rule_chars, settings.max_snippet_chars)
    return recommender.recommend(f"{issue.rule}\n{snippet}", prompt).__dict__


@mcp.tool()
def criar_work_item(issue_key: str, confirmar: bool = False) -> str:
    """Cria a task no Azure DevOps com a recomendação. Só cria com confirmar=True;
    sem isso devolve a pré-visualização do título."""
    issue = _find(issue_key)
    ado = AzureDevOpsClient(settings)
    tag = dedupe_tag(issue)
    if existing := ado.find_by_tag(tag):
        return f"Já existe work item para esta issue: {existing}"
    title = work_item_title(issue)
    if not confirmar:
        return f"Pré-visualização (nada criado): {title}. Chame de novo com confirmar=True para criar."
    snippet = sonar.code_snippet(issue, settings.context_lines)
    prompt = build_user_prompt(issue, sonar.rule_description(issue.rule), snippet,
                               settings.max_rule_chars, settings.max_snippet_chars)
    rec = recommender.recommend(f"{issue.rule}\n{snippet}", prompt)
    created = ado.create(title, work_item_html(issue, rec, snippet), [tag, *settings.ado_extra_tags])
    return f"Work item #{created.get('id')} criado: {title}"


if __name__ == "__main__":
    mcp.run()
