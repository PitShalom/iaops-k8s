"""Coleta determinística de evidências (padrão retrieve-then-reason).

Em vez de deixar o modelo decidir cada ferramenta, o código reúne tudo o que um SRE olharia
primeiro e entrega ao modelo uma única vez. Uma chamada ao LLM, custo e latência previsíveis.
"""
from __future__ import annotations

import json

from . import k8s, memory, prom, rag
from .config import SKILLS_DIR
from .tools import _untrusted


def _skill_for(alertname: str, reason: str) -> str:
    text = f"{alertname} {reason}".lower()
    if "oom" in text:
        return "oom-killed"
    if "crash" in text or reason in ("Error", "CrashLoopBackOff"):
        return "crashloop"
    if "cpu" in text or "throttl" in text:
        return "cpu-throttling"
    return "latency-spike"


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        return f"(falha ao coletar: {type(e).__name__}: {e})"


def collect(alert: dict) -> str:
    ns, pod, wl = alert["namespace"], alert["pod"], alert["workload"]
    status = k8s.pod_status(ns, pod)
    containers = status.get("containers") or [{}]
    c = containers[0]
    reason = (c.get("last_state") or {}).get("reason") or (c.get("current_state") or {}).get("reason") or ""
    skill = _skill_for(alert["alertname"], reason)

    sel = f'namespace="{ns}",pod="{pod}",container!="",container!="POD"'
    pod_sel = f'namespace="{ns}",pod="{pod}"'
    # Container que morre em milissegundos (OOM) não chega a ter série própria no cAdvisor;
    # por isso memória e CPU usam o nível do pod (cgroup), que sempre existe.
    queries = {
        "memoria_working_set_bytes": f"max by (pod) (container_memory_working_set_bytes{{{pod_sel}}})",
        "memoria_limit_bytes": f'kube_pod_container_resource_limits{{{pod_sel},resource="memory"}}',
        "cpu_cores": f"max by (pod) (rate(container_cpu_usage_seconds_total{{{pod_sel}}}[1m]))",
        "cpu_throttling_ratio": (
            f"rate(container_cpu_cfs_throttled_periods_total{{{sel}}}[1m])"
            f"/rate(container_cpu_cfs_periods_total{{{sel}}}[1m])"
        ),
        "restarts": f"kube_pod_container_status_restarts_total{{{pod_sel}}}",
    }
    metrics = {k: _safe(prom.range_analysis, q, 30) for k, q in queries.items()}

    restarted = (c.get("restart_count") or 0) > 0
    logs = _safe(k8s.pod_logs, ns, pod, None, restarted)
    skill_path = SKILLS_DIR / skill / "SKILL.md"
    skill_text = skill_path.read_text(encoding="utf-8") if skill_path.exists() else ""

    parts = [
        f"## Alerta\n{json.dumps({k: alert.get(k) for k in ('alertname','namespace','pod','workload','severity','summary','startsAt')}, ensure_ascii=False)}",
        f"## Estado do pod (get_pod_status)\n{json.dumps(status, ensure_ascii=False, default=str)}",
        f"## Logs {'do container anterior' if restarted else 'atuais'} (get_pod_logs)\n{_untrusted('logs:' + pod, logs)}",
        f"## Eventos (get_events)\n{_untrusted('events:' + pod, _safe(k8s.pod_events, ns, pod))}",
        f"## Métricas dos últimos 30 min (detect_anomaly)\n{json.dumps(metrics, ensure_ascii=False, default=str)}",
        f"## Runbooks (search_runbooks)\n{json.dumps(rag.search(f'{alert['alertname']} {reason} {skill}'), ensure_ascii=False)}",
        f"## Incidentes anteriores do workload (recall_incidents)\n{json.dumps(memory.recall(ns, wl), ensure_ascii=False)}",
        f"## Skill de investigação: {skill}\n{skill_text}",
    ]
    return "\n\n".join(parts)
