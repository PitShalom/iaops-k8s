"""Ferramentas expostas ao Claude e o despachante que as executa.

Todas são somente leitura. Resultados que carregam texto controlado por terceiros
(logs, eventos) são marcados como <untrusted_data> para reduzir risco de prompt injection.
"""
from __future__ import annotations

import json

from . import k8s, memory, prom, rag
from .config import CONFIG_DIR, SKILLS_DIR, TOOL_RESULT_MAX_CHARS

_schema = json.loads((CONFIG_DIR / "incident.schema.json").read_text(encoding="utf-8"))
_schema.pop("$schema", None)
_schema.pop("title", None)

TOOLS = [
    {
        "name": "load_skill",
        "description": "Carrega o guia de investigação (skill) de um tipo de falha: "
        "oom-killed, crashloop, cpu-throttling, latency-spike. Chame uma vez, cedo.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "get_pod_status",
        "description": "Estado atual do pod: fase, restarts, estado atual e último estado "
        "(exitCode/reason), limits e requests, probes.",
        "input_schema": {
            "type": "object",
            "properties": {"namespace": {"type": "string"}, "pod": {"type": "string"}},
            "required": ["namespace", "pod"],
        },
    },
    {
        "name": "get_pod_logs",
        "description": "Últimas linhas de log do container. Use previous=true para o container "
        "que acabou de morrer (essencial em CrashLoop/OOM).",
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string"},
                "pod": {"type": "string"},
                "previous": {"type": "boolean", "default": False},
            },
            "required": ["namespace", "pod"],
        },
    },
    {
        "name": "get_events",
        "description": "Eventos recentes do Kubernetes para o pod (linha do tempo do kubelet).",
        "input_schema": {
            "type": "object",
            "properties": {"namespace": {"type": "string"}, "pod": {"type": "string"}},
            "required": ["namespace", "pod"],
        },
    },
    {
        "name": "prometheus_query",
        "description": "Consulta instantânea PromQL. Retorna até 10 séries.",
        "input_schema": {
            "type": "object",
            "properties": {"promql": {"type": "string"}},
            "required": ["promql"],
        },
    },
    {
        "name": "detect_anomaly",
        "description": "Executa uma consulta PromQL numa janela (minutos) e retorna, por série, "
        "z-score contra a linha de base, média recente, máximo e tendência.",
        "input_schema": {
            "type": "object",
            "properties": {
                "promql": {"type": "string"},
                "minutes": {"type": "integer", "default": 60},
            },
            "required": ["promql"],
        },
    },
    {
        "name": "search_runbooks",
        "description": "Busca nos runbooks internos. Retorna trechos com fonte para citar.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "recall_incidents",
        "description": "Incidentes anteriores do mesmo workload (memória), com diagnóstico e feedback. "
        "Use para detectar recorrência.",
        "input_schema": {
            "type": "object",
            "properties": {"namespace": {"type": "string"}, "workload": {"type": "string"}},
            "required": ["namespace", "workload"],
        },
    },
    {
        "name": "submit_diagnosis",
        "description": "Entrega o diagnóstico final. Chame exatamente uma vez, ao terminar. "
        "Toda evidência precisa citar a fonte (ferramenta ou runbook).",
        "input_schema": _schema,
    },
]


def _untrusted(source: str, payload) -> str:
    body = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, default=str)
    return f'<untrusted_data source="{source}">\n{body}\n</untrusted_data>'


def execute(name: str, args: dict) -> str:
    """Executa uma ferramenta e devolve texto (sempre truncado e sem exceções)."""
    try:
        out = _dispatch(name, args)
    except Exception as e:  # o modelo precisa ver o erro para se adaptar
        out = f"ERRO ao executar {name}: {type(e).__name__}: {e}"
    if len(out) > TOOL_RESULT_MAX_CHARS:
        out = out[:TOOL_RESULT_MAX_CHARS] + "\n...[truncado]"
    return out


def _dispatch(name: str, a: dict) -> str:
    if name == "load_skill":
        skill = a["name"].strip().replace("/", "").replace("..", "")
        path = SKILLS_DIR / skill / "SKILL.md"
        return path.read_text(encoding="utf-8") if path.exists() else f"skill '{skill}' não existe"
    if name == "get_pod_status":
        return json.dumps(k8s.pod_status(a["namespace"], a["pod"]), ensure_ascii=False, default=str)
    if name == "get_pod_logs":
        logs = k8s.pod_logs(a["namespace"], a["pod"], previous=bool(a.get("previous", False)))
        return _untrusted(f"logs:{a['pod']}", logs)
    if name == "get_events":
        return _untrusted(f"events:{a['pod']}", k8s.pod_events(a["namespace"], a["pod"]))
    if name == "prometheus_query":
        return json.dumps(prom.instant(a["promql"]), ensure_ascii=False)
    if name == "detect_anomaly":
        return json.dumps(
            prom.range_analysis(a["promql"], int(a.get("minutes", 60))), ensure_ascii=False
        )
    if name == "search_runbooks":
        return json.dumps(rag.search(a["query"]), ensure_ascii=False)
    if name == "recall_incidents":
        return json.dumps(memory.recall(a["namespace"], a["workload"]), ensure_ascii=False)
    return f"ferramenta desconhecida: {name}"
