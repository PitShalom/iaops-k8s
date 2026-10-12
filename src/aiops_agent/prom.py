"""Cliente do Prometheus. Devolve resumos compactos, nunca séries cruas (economiza tokens)."""
from __future__ import annotations

import time

import httpx

from .anomaly import analyze
from .config import PROMETHEUS_URL


def _get(path: str, params: dict) -> dict:
    r = httpx.get(f"{PROMETHEUS_URL}{path}", params=params, timeout=10)
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "success":
        raise RuntimeError(body.get("error", "erro no Prometheus"))
    return body["data"]


def _label_summary(metric: dict) -> dict:
    keep = ("pod", "container", "namespace", "reason", "alertname")
    return {k: v for k, v in metric.items() if k in keep}


def instant(promql: str, limit: int = 10) -> list[dict]:
    data = _get("/api/v1/query", {"query": promql})
    out = []
    for r in data["result"][:limit]:
        out.append({"labels": _label_summary(r["metric"]), "value": r["value"][1]})
    return out


def range_analysis(promql: str, minutes: int = 60, step: str = "30s") -> list[dict]:
    end = time.time()
    data = _get(
        "/api/v1/query_range",
        {"query": promql, "start": end - minutes * 60, "end": end, "step": step},
    )
    out = []
    for r in data["result"][:5]:
        values = [float(v[1]) for v in r["values"] if v[1] not in ("NaN", "+Inf", "-Inf")]
        out.append({"labels": _label_summary(r["metric"]), **analyze(values)})
    return out
