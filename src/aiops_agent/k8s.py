"""Coletor Kubernetes: somente leitura (o RBAC do agente não permite mais que isso)."""
from __future__ import annotations

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from .config import LOG_TAIL_LINES
from .redact import redact

_core: client.CoreV1Api | None = None


def _api() -> client.CoreV1Api:
    global _core
    if _core is None:
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        _core = client.CoreV1Api()
    return _core


def workload_of(pod_name: str) -> str:
    """payments-api-779bd9cd59-brlbb -> payments-api (remove hash do ReplicaSet e do pod)."""
    parts = pod_name.split("-")
    return "-".join(parts[:-2]) if len(parts) > 2 else pod_name


def _state_dict(state) -> dict:
    if state is None:
        return {}
    for kind in ("waiting", "terminated", "running"):
        s = getattr(state, kind, None)
        if s is not None:
            d = {"state": kind}
            for f in ("reason", "message", "exit_code", "signal"):
                v = getattr(s, f, None)
                if v not in (None, ""):
                    d[f] = v
            return d
    return {}


def pod_status(namespace: str, pod: str) -> dict:
    try:
        p = _api().read_namespaced_pod(pod, namespace)
    except ApiException as e:
        return {"error": f"{e.status} {e.reason}"}
    containers = []
    specs = {c.name: c for c in p.spec.containers}
    for cs in p.status.container_statuses or []:
        spec = specs.get(cs.name)
        res = spec.resources if spec else None
        containers.append(
            {
                "name": cs.name,
                "image": cs.image,
                "ready": cs.ready,
                "restart_count": cs.restart_count,
                "current_state": _state_dict(cs.state),
                "last_state": _state_dict(cs.last_state),
                "limits": dict(res.limits or {}) if res else {},
                "requests": dict(res.requests or {}) if res else {},
                "has_liveness_probe": bool(spec and spec.liveness_probe),
                "has_readiness_probe": bool(spec and spec.readiness_probe),
            }
        )
    return {
        "pod": pod,
        "namespace": namespace,
        "phase": p.status.phase,
        "node": p.spec.node_name,
        "started": str(p.status.start_time),
        "owner": [f"{o.kind}/{o.name}" for o in (p.metadata.owner_references or [])],
        "containers": containers,
    }


def pod_logs(namespace: str, pod: str, container: str | None = None, previous: bool = False) -> str:
    try:
        text = _api().read_namespaced_pod_log(
            pod, namespace, container=container, previous=previous, tail_lines=LOG_TAIL_LINES
        )
    except ApiException as e:
        return f"(sem logs: {e.status} {e.reason})"
    return redact(text or "(logs vazios)")


def pod_events(namespace: str, pod: str, limit: int = 15) -> list[dict]:
    try:
        evs = _api().list_namespaced_event(namespace, field_selector=f"involvedObject.name={pod}").items
    except ApiException as e:
        return [{"error": f"{e.status} {e.reason}"}]
    evs.sort(key=lambda e: e.last_timestamp or e.event_time or e.metadata.creation_timestamp)
    return [
        {
            "type": e.type,
            "reason": e.reason,
            "message": redact(e.message or ""),
            "count": e.count,
            "last": str(e.last_timestamp or e.event_time),
        }
        for e in evs[-limit:]
    ]
