"""Loop do agente: Claude investiga chamando ferramentas até entregar o diagnóstico.

Se não houver chave, a API falhar ou o orçamento estourar, cai para diagnóstico por regras.
"""
from __future__ import annotations

import subprocess
import time

import anthropic

from . import cli_backend, k8s, memory, tools
from .agent_prompt import SYSTEM_PROMPT as BASE_PROMPT
from .config import (
    ANTHROPIC_API_KEY,
    CLAUDE_CODE_OAUTH_TOKEN,
    LLM_BACKEND,
    MAX_TOKENS_INCIDENT,
    MAX_TURNS,
    MODEL,
)

SYSTEM_PROMPT = BASE_PROMPT + """
Método (use as ferramentas):
1. Carregue a skill adequada ao tipo de falha (load_skill).
2. Colete evidências: estado do pod, logs (previous=true se reiniciou), eventos, métricas.
3. Verifique recorrência (recall_incidents) e consulte runbooks (search_runbooks).
4. Entregue o diagnóstico com submit_diagnosis.
Seja eficiente: não repita chamadas e finalize assim que tiver evidência suficiente.
"""


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=2, timeout=60)


def _alert_prompt(alert: dict) -> str:
    return (
        "Novo alerta do Alertmanager. Investigue.\n\n"
        f"alertname: {alert['alertname']}\n"
        f"namespace: {alert['namespace']}\n"
        f"pod: {alert['pod']}\n"
        f"workload: {alert['workload']}\n"
        f"severity: {alert.get('severity', '?')}\n"
        f"summary: {alert.get('summary', '')}\n"
        f"startsAt: {alert.get('startsAt', '')}\n"
    )


def _backends() -> list[str]:
    """Ordem de tentativa. 'auto' prefere a assinatura (cli) e usa a API paga como segunda opção."""
    if LLM_BACKEND == "rules":
        return []
    available = []
    if CLAUDE_CODE_OAUTH_TOKEN:
        available.append("cli")
    if ANTHROPIC_API_KEY:
        available.append("api")
    if LLM_BACKEND in ("cli", "api"):
        return [b for b in available if b == LLM_BACKEND]
    return available


def investigate(alert: dict) -> tuple[dict, dict]:
    """Retorna (diagnostico, metadados_da_execucao)."""
    started = time.time()
    reasons: list[str] = []

    for backend in _backends():
        meta = {"model": MODEL, "mode": backend, "turns": 0, "input_tokens": 0, "output_tokens": 0, "tools": []}
        try:
            diagnosis = cli_backend.diagnose(alert, meta) if backend == "cli" else _llm_loop(alert, meta)
        except Exception as e:  # rede, quota, schema inválido...
            print(f"[{backend}] falhou: {type(e).__name__}: {e}", flush=True)
            reasons.append(f"{backend}: {_short_reason(e)}")
            continue
        meta["duration_s"] = round(time.time() - started, 1)
        return diagnosis, meta

    meta = {"model": None, "mode": "rules", "turns": 0, "input_tokens": 0, "output_tokens": 0, "tools": []}
    return _fallback(alert, meta, started, "; ".join(reasons) or "nenhum backend LLM configurado")


def _short_reason(e: Exception) -> str:
    """Motivo curto e legível para o relatório (o erro completo vai para o log)."""
    msg = str(e).lower()
    if "credit balance" in msg:
        return "créditos da API Anthropic insuficientes"
    if isinstance(e, subprocess.TimeoutExpired):
        return "tempo esgotado na CLI"
    if "claude cli" in msg:
        return "falha na CLI do Claude"
    if isinstance(e, anthropic.AuthenticationError):
        return "chave da API inválida"
    if isinstance(e, anthropic.RateLimitError):
        return "limite de requisições da API"
    if isinstance(e, anthropic.APIConnectionError):
        return "sem conexão com a API"
    return type(e).__name__


def _llm_loop(alert: dict, meta: dict) -> dict:
    client = _client()
    messages = [{"role": "user", "content": _alert_prompt(alert)}]
    system = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]
    nudged = False

    for _ in range(MAX_TURNS):
        resp = client.messages.create(
            model=MODEL, max_tokens=2000, system=system, tools=tools.TOOLS, messages=messages
        )
        meta["turns"] += 1
        meta["input_tokens"] += resp.usage.input_tokens
        meta["output_tokens"] += resp.usage.output_tokens
        if meta["input_tokens"] + meta["output_tokens"] > MAX_TOKENS_INCIDENT:
            raise RuntimeError(f"orçamento de tokens excedido ({MAX_TOKENS_INCIDENT})")

        calls = [b for b in resp.content if b.type == "tool_use"]
        for call in calls:
            if call.name == "submit_diagnosis":
                meta["tools"].append("submit_diagnosis")
                return dict(call.input)

        if not calls:
            if nudged:
                raise RuntimeError("o modelo encerrou sem submit_diagnosis")
            nudged = True
            messages.append({"role": "assistant", "content": resp.content})
            messages.append({"role": "user", "content": "Entregue agora o diagnóstico via submit_diagnosis."})
            continue

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for call in calls:
            meta["tools"].append(call.name)
            results.append(
                {"type": "tool_result", "tool_use_id": call.id, "content": tools.execute(call.name, call.input)}
            )
        messages.append({"role": "user", "content": results})

    raise RuntimeError(f"limite de {MAX_TURNS} turnos atingido")


# ---------- fallback por regras ----------

def _fallback(alert: dict, meta: dict, started: float, why: str) -> tuple[dict, dict]:
    ns, pod = alert["namespace"], alert["pod"]
    status = k8s.pod_status(ns, pod)
    containers = status.get("containers") or [{}]
    c = containers[0]
    last, cur = c.get("last_state", {}), c.get("current_state", {})
    reason = last.get("reason") or cur.get("reason") or ""
    evid = [{"fonte": "get_pod_status", "detalhe": f"restarts={c.get('restart_count')} "
             f"estado={cur} último_estado={last} limits={c.get('limits')}"}]

    alertname = alert["alertname"]
    if reason == "OOMKilled" or "OOM" in alertname:
        tipo, sev = "oom", "alta"
        causa = f"Container encerrado por falta de memória (OOMKilled); limit atual: {c.get('limits', {}).get('memory')}."
        acao = "Aumentar o limit de memória com margem sobre o pico observado e investigar vazamento se o uso crescer continuamente."
    elif "CrashLoop" in alertname or reason in ("Error", "CrashLoopBackOff"):
        logs = k8s.pod_logs(ns, pod, previous=True)
        tipo, sev = "crashloop", "media"
        causa = "Container reiniciando repetidamente; veja as últimas linhas do log do container anterior."
        acao = "Corrigir o erro indicado nos logs (configuração, dependência ou probe) e reimplantar."
        evid.append({"fonte": "get_pod_logs", "detalhe": logs[-400:]})
    elif "CPU" in alertname or "Throttl" in alertname:
        tipo, sev = "cpu", "media"
        causa = "Container com throttling de CPU: carga acima do limit configurado."
        acao = "Ajustar limit/request de CPU com base no p95 ou habilitar HPA."
    else:
        tipo, sev = "outro", "media"
        causa = "Não foi possível classificar automaticamente."
        acao = "Investigar manualmente o pod e os eventos."

    diagnosis = {
        "resumo": f"[regras] {alertname} em {ns}/{alert['workload']} ({why})"[:300],
        "tipo": tipo,
        "severidade": sev,
        "causa_provavel": causa,
        "evidencias": evid,
        "acao_sugerida": acao,
        "recorrencia": len(memory.recall(ns, alert["workload"])),
        "confianca": 0.4,
    }
    meta.update({"mode": "rules", "duration_s": round(time.time() - started, 1)})
    return diagnosis, meta
