"""Memória de longo prazo: incidentes anteriores em SQLite (persistido em PVC)."""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager

from .config import DATA_DIR

_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
  id TEXT PRIMARY KEY, ts REAL, namespace TEXT, workload TEXT, alertname TEXT,
  tipo TEXT, severidade TEXT, causa TEXT, acao TEXT, confianca REAL,
  mode TEXT, diagnosis_json TEXT, report_path TEXT, feedback TEXT
);
CREATE INDEX IF NOT EXISTS idx_inc_wl ON incidents(namespace, workload, ts);
CREATE TABLE IF NOT EXISTS agent_runs (
  incident_id TEXT, model TEXT, mode TEXT, turns INTEGER,
  input_tokens INTEGER, output_tokens INTEGER, duration_s REAL, tools TEXT
);
"""


@contextmanager
def _db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATA_DIR / "memory.db")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def recall(namespace: str, workload: str, limit: int = 5) -> list[dict]:
    with _db() as c:
        rows = c.execute(
            "SELECT id, ts, alertname, tipo, severidade, causa, acao, feedback FROM incidents "
            "WHERE namespace=? AND workload=? ORDER BY ts DESC LIMIT ?",
            (namespace, workload, limit),
        ).fetchall()
    return [
        {**dict(r), "quando": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(r["ts"])) + " UTC"}
        for r in rows
    ]


def last_seen(namespace: str, workload: str) -> float | None:
    with _db() as c:
        r = c.execute(
            "SELECT MAX(ts) FROM incidents WHERE namespace=? AND workload=?", (namespace, workload)
        ).fetchone()
    return r[0]


def save_incident(inc: dict) -> None:
    d = inc["diagnosis"]
    with _db() as c:
        c.execute(
            "INSERT OR REPLACE INTO incidents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                inc["id"], inc["ts"], inc["namespace"], inc["workload"], inc["alertname"],
                d.get("tipo"), d.get("severidade"), d.get("causa_provavel"), d.get("acao_sugerida"),
                d.get("confianca"), inc["mode"], json.dumps(d, ensure_ascii=False),
                inc.get("report_path"), None,
            ),
        )


def save_run(incident_id: str, run: dict) -> None:
    with _db() as c:
        c.execute(
            "INSERT INTO agent_runs VALUES (?,?,?,?,?,?,?,?)",
            (incident_id, run.get("model"), run.get("mode"), run.get("turns"),
             run.get("input_tokens"), run.get("output_tokens"), run.get("duration_s"),
             json.dumps(run.get("tools", []))),
        )


def list_incidents(limit: int = 50) -> list[dict]:
    with _db() as c:
        rows = c.execute(
            "SELECT id, ts, namespace, workload, alertname, tipo, severidade, confianca, mode, feedback "
            "FROM incidents ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_incident(incident_id: str) -> dict | None:
    with _db() as c:
        r = c.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
    return dict(r) if r else None


def set_feedback(incident_id: str, feedback: str) -> bool:
    with _db() as c:
        cur = c.execute("UPDATE incidents SET feedback=? WHERE id=?", (feedback, incident_id))
    return cur.rowcount > 0
