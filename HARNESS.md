# IAops-1 — Harness do Agente AIOps

> **Status:** este documento é a **especificação de desenho-alvo**. A implementação atual é mais
> simples: coleta determinística de evidências + uma chamada ao modelo (backend `cli`) ou loop de
> tool use direto (backend `api`), com clientes nativos de Kubernetes/Prometheus em vez de
> servidores MCP, e sem subagentes separados. Veja "Especificação vs. implementação" no README.

Agente que recebe alertas do Alertmanager (Kind + kube-prometheus-stack), investiga o cluster
em modo somente leitura e produz um diagnóstico de causa raiz usando a Claude API.

## 1. Arquitetura

```
Alertmanager ─webhook→ [Gateway FastAPI]
                            │ dedupe + fingerprint
                            ▼
                    [Orquestrador Claude]  ◄── Memória (SQLite) ── incidentes passados
                      │   │   │   │
        ┌─────────────┘   │   │   └──────────────┐
        ▼                 ▼   ▼                  ▼
  k8s-investigator   metrics-analyst   runbook-researcher   reporter
        │                 │                  │                │
   MCP Kubernetes    MCP Prometheus      RAG (runbooks)   Markdown/Grafana
```

## 2. Loop do agente

| Item | Decisão |
|---|---|
| Implementação | Anthropic Python SDK, loop manual de tool use (`messages.create` + `tool_use`/`tool_result`) |
| Orquestrador | `claude-sonnet-5-5` (planeja e sintetiza) |
| Subagentes | `claude-haiku-5-5` (coleta e análise) |
| Limites | 8 turnos por subagente, 20 por incidente, ~30k tokens por incidente |
| Saída final | JSON validado por schema (`config/incident.schema.json`) |
| Prompt caching | `cache_control` no system prompt e nas skills |
| Fallback | Sem chave/rede/orçamento estourado: diagnóstico por regras |

## 3. Subagentes

Definições em `agents/`. Cada subagente tem prompt, ferramentas e limite de turnos próprios,
e contexto isolado: o orquestrador passa só o necessário e recebe resumos curtos.

| Subagente | Responsabilidade | Ferramentas |
|---|---|---|
| `triage` | Classifica tipo/severidade e define o plano | nenhuma |
| `k8s-investigator` | Estado do pod, eventos, logs, describe | MCP Kubernetes (read-only) |
| `metrics-analyst` | CPU/mem/restarts/latência + anomalias | MCP Prometheus, `detect_anomaly` |
| `runbook-researcher` | Runbooks e incidentes similares | `search_runbooks`, `recall_incidents` |
| `reporter` | Diagnóstico final e relatório | `write_report`, `annotate_grafana` |

## 4. Skills

Em `skills/<nome>/SKILL.md`, carregadas sob demanda pelo `triage` conforme o tipo do alerta:
`oom-killed`, `crashloop`, `cpu-throttling`, `latency-spike`, `report-format`.

## 5. MCP e ferramentas

Configuração em `config/mcp.json`.

| Servidor / tool | Origem | Modo |
|---|---|---|
| Kubernetes MCP | github.com/containers/kubernetes-mcp-server | `--read-only` + RBAC restrito |
| Prometheus MCP | github.com/pab1it0/prometheus-mcp-server | somente `query` / `query_range` |
| `detect_anomaly` | código local (numpy/scikit-learn) | função local |
| `search_runbooks` | código local | RAG |
| `recall_incidents` | código local | memória |
| `write_report` / `annotate_grafana` | código local | escrita só em `/reports` e Grafana |

Nenhuma ferramenta muta o cluster. Remediação é apenas sugestão.

## 6. RAG

| Item | Decisão |
|---|---|
| Corpus | 8–10 runbooks Markdown próprios (`rag/runbooks/`) + trechos da doc oficial de troubleshooting do K8s |
| Chunking | Por seção de cabeçalho (~300 tokens) |
| Recuperação | BM25 + TF-IDF (`rank_bm25`/scikit-learn): sem vetor DB, sem GPU, sem custo |
| Citação | Todo trecho carrega `fonte#seção`; o diagnóstico deve citá-lo |
| Evolução | Embeddings + Chroma como próximo passo |

## 7. Memória e histórico

| Camada | Armazenamento | Uso |
|---|---|---|
| Curto prazo | Mensagens do loop, por incidente | Contexto da investigação atual |
| Longo prazo | SQLite em PVC (hostPath no Kind) | Fingerprint, tipo, causa, ação, data |
| Recorrência | Consulta por fingerprint `namespace/workload/alertname` | "3º OOM deste deploy em 24h" |
| Feedback | `POST /incidents/{id}/feedback` | Marca diagnóstico correto/incorreto |
| Auditoria | Tabela `agent_runs` | Prompt, tools, tokens, custo, latência |

## 8. Guardrails

- Somente leitura no cluster (RBAC + `--read-only` no MCP).
- Redação de segredos (regex para tokens/senhas) antes de enviar logs ao Claude.
- Logs truncados (últimas N linhas) para controlar tokens.
- Orçamento de tokens/turnos com corte e fallback por regras.
- Dedupe e rate limit: mesmo fingerprint em 5 min vira um incidente.
- Schema estrito na saída; JSON inválido gera uma retentativa e depois fallback.
- Prompt injection: conteúdo de logs/eventos é tratado como dado não confiável, nunca como instrução.
- `ANTHROPIC_API_KEY` apenas como Secret do K8s, nunca commitada.

## 9. Estrutura do repositório

```
IAops-1/
├── HARNESS.md
├── agents/            # definição dos subagentes
├── skills/            # skills carregadas sob demanda
├── rag/runbooks/      # corpus do RAG
├── config/            # mcp.json, schema de saída, limites
├── src/               # (a criar) gateway, loop, tools, memória, rag
├── k8s/               # (a criar) manifests, RBAC, values do Helm
├── chaos/             # (a criar) app alvo com falhas
└── Makefile           # (a criar) up / chaos / down
```

## 10. Prioridades para caber em 2h

| Prioridade | Itens |
|---|---|
| P0 | Gateway, loop do orquestrador, `k8s-investigator`, `metrics-analyst`, `reporter`, schema, guardrails básicos |
| P1 | `triage` + skills, RAG por BM25, memória SQLite com recorrência |
| P2 | Painel/annotation no Grafana, endpoint de feedback, auditoria detalhada |
