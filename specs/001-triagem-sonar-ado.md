# SPEC 001 — Triagem de vulnerabilidades do SonarQube com IA e abertura de work items no Azure DevOps

> Projeto desenvolvido com **Spec Driven Development**: esta especificação foi escrita antes do código
> e serve de contrato para implementação, testes e revisão. Mudança de comportamento começa aqui.

## 1. Contexto

Times de AppSec recebem do SonarQube centenas de issues de segurança. Para cada uma, alguém precisa
abrir o Sonar, entender a regra, olhar o trecho de código, escrever uma orientação de correção e
criar uma task para o time dono do projeto. É um trabalho repetitivo, e a qualidade da orientação
varia de pessoa para pessoa.

## 2. Objetivo

Automatizar o fluxo **Sonar → recomendação de correção gerada por LLM → work item no Azure DevOps**,
mantendo o analista no controle (simulação por padrão) e garantindo que nenhuma issue gere task duplicada.

## 3. Escopo

**Dentro:** buscar issues de segurança abertas; enriquecer com descrição da regra e trecho de código;
gerar recomendação estruturada com LLM; criar work item com a recomendação no corpo; evitar duplicidade;
expor as mesmas capacidades para agentes de IA via MCP (Model Context Protocol).

**Fora:** corrigir código automaticamente, abrir pull requests, fechar work items de issues resolvidas (roadmap).

## 4. Requisitos funcionais

| ID | Requisito |
|----|-----------|
| RF01 | Listar issues com `impactSoftwareQualities=SECURITY`, com status e severidades configuráveis. |
| RF02 | Filtrar por projetos e limitar a quantidade de issues por execução (`--limit`). |
| RF03 | Obter a descrição de cada regra uma única vez por execução (cache por regra). |
| RF04 | Obter linhas de contexto ao redor da linha apontada (padrão: 8 antes e 8 depois). |
| RF05 | Pedir ao LLM resposta **somente em JSON** com `resumo`, `risco`, `passos_correcao`, `exemplo_codigo`, `referencias`, `confianca`. |
| RF06 | Rejeitar resposta fora do schema: a issue vira falha e o lote continua. |
| RF07 | Antes de criar, consultar via WIQL se já existe work item com a tag `sonar-key:<key>`. Se existir, pular. |
| RF08 | Rodar em **simulação** por padrão (pré-visualização HTML em `output/`). Criar no Azure DevOps só com `--apply`. |
| RF09 | Ao final, mostrar criadas, puladas, falhas, tokens de entrada/saída e chamadas economizadas pelo cache. |
| RF10 | `--demo` executa o fluxo inteiro com dados fictícios, sem credenciais e sem rede. |

## 5. Requisitos não funcionais

| ID | Requisito |
|----|-----------|
| RNF01 | **Segredos** só por variáveis de ambiente (`.env` fora do versionamento). |
| RNF02 | **Prompt injection:** código e descrição da regra são dados não confiáveis, enviados delimitados; o prompt de sistema manda ignorar instruções contidas neles; a saída passa por validação de schema. |
| RNF03 | **XSS no work item:** todo texto vindo do Sonar ou do LLM é escapado (`html.escape`) antes de compor o HTML. |
| RNF04 | **Custo de tokens:** trechos e descrições são truncados; recomendações ficam em cache local por hash de (modelo + regra + trecho). |
| RNF05 | **Privacidade:** só o trecho necessário vai para o provedor de LLM. Para código proprietário, validar antes a política da empresa sobre provedores externos. |
| RNF06 | **Resiliência:** timeout em toda chamada HTTP; falha em uma issue não interrompe o lote. |

## 6. Critérios de aceite

1. **Dado** uma issue sem work item, **quando** executo com `--apply`, **então** é criado um item com título `[Sonar][<severidade>] <regra> em <arquivo>:<linha>`, tag `sonar-key:<key>` e a recomendação no corpo.
2. **Dado** que já existe work item com a tag da issue, **quando** executo de novo, **então** nada é criado e a issue aparece como pulada.
3. **Dado** que o LLM devolve texto que não é JSON válido, **quando** a issue é processada, **então** ela vira falha e as demais continuam.
4. **Dado** um trecho com `<script>alert(1)</script>`, **quando** o HTML é gerado, **então** o conteúdo aparece escapado.
5. **Dado** duas issues com mesma regra e mesmo trecho, **quando** processadas, **então** o LLM é chamado uma vez só.
6. **Dado** que nenhuma credencial está configurada, **quando** executo `--demo`, **então** o fluxo roda e gera as pré-visualizações.

## 7. Decisões de design

- **Simulação como padrão:** criar tasks em lote é difícil de desfazer; o analista revisa antes.
- **Tag como chave de idempotência:** não depende de campo customizado no processo do Azure DevOps.
- **Provedor de LLM atrás de uma interface:** troca de modelo/provedor sem mexer no fluxo e testes com provedor offline.
- **JSON estruturado em vez de texto livre:** dá para validar, renderizar de forma consistente e medir qualidade.

## 8. Roadmap

- Fechar ou comentar o work item quando a issue sumir do Sonar.
- Definir área/time automaticamente a partir do histórico de commits.
- Eval da qualidade das recomendações com um conjunto de issues rotuladas.
