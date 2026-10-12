"""API do agente: recebe webhooks do Alertmanager e expõe os incidentes diagnosticados."""
from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from . import agent, k8s, memory
from .config import DEDUPE_WINDOW_SECONDS, REPORTS_DIR, WATCH_NAMESPACES
from .k8s import workload_of

app = FastAPI(title="IAops-1 agent")


class DiagnoseRequest(BaseModel):
    namespace: str = "demo"
    pod: str
    alertname: str = "ManualDiagnose"


class Feedback(BaseModel):
    correct: bool


def _render_report(inc: dict, run: dict) -> str:
    d = inc["diagnosis"]
    ev = "\n".join(f"- [{e['fonte']}] {e['detalhe']}" for e in d.get("evidencias", [])) or "- (sem evidências)"
    return (
        f"# Incidente: {inc['alertname']} — {inc['namespace']}/{inc['workload']}\n"
        f"Severidade: {d['severidade']}   Confiança: {d['confianca']}   "
        f"Recorrência: {d.get('recorrencia', 0)}   Modo: {inc['mode']}\n\n"
        f"## Resumo\n{d['resumo']}\n\n"
        f"## Causa provável\n{d['causa_provavel']}\n\n"
        f"## Evidências\n{ev}\n\n"
        f"## Ação sugerida\n{d['acao_sugerida']}\n\n"
        f"---\n_Pod: {inc['pod']} · modelo: {run.get('model')} · turnos: {run.get('turns')} · "
        f"tokens: {run.get('input_tokens')}+{run.get('output_tokens')} · "
        f"ferramentas: {', '.join(run.get('tools', []))}_\n"
    )


def process_alert(alert: dict) -> dict:
    diagnosis, run = agent.investigate(alert)
    inc = {
        "id": uuid.uuid4().hex[:12],
        "ts": time.time(),
        "namespace": alert["namespace"],
        "workload": alert["workload"],
        "pod": alert["pod"],
        "alertname": alert["alertname"],
        "mode": run["mode"],
        "diagnosis": diagnosis,
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = Path(REPORTS_DIR) / f"{inc['id']}.md"
    path.write_text(_render_report(inc, run), encoding="utf-8")
    inc["report_path"] = str(path)
    memory.save_incident(inc)
    memory.save_run(inc["id"], run)
    print(f"[incidente {inc['id']}] {inc['alertname']} {inc['namespace']}/{inc['workload']} "
          f"-> {diagnosis['tipo']} ({run['mode']}, {run['turns']} turnos, "
          f"{run['input_tokens']}+{run['output_tokens']} tokens)", flush=True)
    return inc


_claimed: dict[tuple[str, str], float] = {}
_claim_lock = threading.Lock()


def _claim(namespace: str, workload: str) -> bool:
    """Reserva o workload no momento da aceitação (e não ao fim do diagnóstico),
    para que alertas simultâneos do mesmo workload não disparem investigações duplicadas."""
    key, now = (namespace, workload), time.time()
    with _claim_lock:
        if now - _claimed.get(key, 0) < DEDUPE_WINDOW_SECONDS:
            return False
        _claimed[key] = now
        return True


def _from_labels(labels: dict, annotations: dict, starts: str = "") -> dict | None:
    ns, pod = labels.get("namespace"), labels.get("pod")
    if not ns or not pod or ns not in WATCH_NAMESPACES:
        return None
    return {
        "alertname": labels.get("alertname", "?"),
        "namespace": ns,
        "pod": pod,
        "workload": workload_of(pod),
        "severity": labels.get("severity"),
        "summary": annotations.get("summary", ""),
        "startsAt": starts,
    }


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/webhook")
def webhook(payload: dict, background: BackgroundTasks):
    accepted, skipped = [], 0
    for a in payload.get("alerts", []):
        if a.get("status") != "firing":
            continue
        alert = _from_labels(a.get("labels", {}), a.get("annotations", {}), a.get("startsAt", ""))
        # o label "pod" de alguns alertas aponta para o exporter, não para um pod do namespace
        if not alert or "error" in k8s.pod_status(alert["namespace"], alert["pod"]):
            skipped += 1
            continue
        if not _claim(alert["namespace"], alert["workload"]):
            skipped += 1  # dedupe: um incidente por workload dentro da janela
            continue
        accepted.append(f"{alert['namespace']}/{alert['workload']}:{alert['alertname']}")
        background.add_task(process_alert, alert)
    return {"accepted": accepted, "skipped": skipped}


@app.post("/diagnose")
def diagnose(req: DiagnoseRequest):
    """Diagnóstico síncrono sob demanda (útil para testes e demos)."""
    alert = {
        "alertname": req.alertname,
        "namespace": req.namespace,
        "pod": req.pod,
        "workload": workload_of(req.pod),
    }
    inc = process_alert(alert)
    return {"id": inc["id"], "mode": inc["mode"], "diagnosis": inc["diagnosis"]}


@app.get("/incidents")
def incidents():
    return memory.list_incidents()


@app.get("/incidents/{incident_id}")
def incident(incident_id: str):
    inc = memory.get_incident(incident_id)
    if not inc:
        raise HTTPException(404, "incidente não encontrado")
    return inc


@app.get("/incidents/{incident_id}/report", response_class=PlainTextResponse)
def report(incident_id: str):
    inc = memory.get_incident(incident_id)
    if not inc or not inc.get("report_path"):
        raise HTTPException(404, "relatório não encontrado")
    return Path(inc["report_path"]).read_text(encoding="utf-8")


@app.post("/incidents/{incident_id}/feedback")
def feedback(incident_id: str, body: Feedback):
    if not memory.set_feedback(incident_id, "correto" if body.correct else "incorreto"):
        raise HTTPException(404, "incidente não encontrado")
    return {"ok": True}
