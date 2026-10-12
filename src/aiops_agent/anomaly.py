"""Detecção de anomalias simples e explicável: z-score contra a linha de base + tendência.

Escolha deliberada por estatística clássica em vez de ML: é auditável, não precisa de
treino e funciona com poucas amostras (incidentes novos têm pouco histórico).
"""
from __future__ import annotations

from statistics import mean, pstdev


def _slope(values: list[float]) -> float:
    """Inclinação da regressão linear (unidade por amostra)."""
    n = len(values)
    if n < 2:
        return 0.0
    xm, ym = (n - 1) / 2, mean(values)
    den = sum((i - xm) ** 2 for i in range(n))
    return sum((i - xm) * (v - ym) for i, v in enumerate(values)) / den if den else 0.0


def analyze(values: list[float], z_threshold: float = 3.0) -> dict:
    if len(values) < 8:
        return {"anomalous": False, "reason": f"amostras insuficientes ({len(values)})"}
    cut = int(len(values) * 0.7)
    base, recent = values[:cut], values[cut:]
    mu, sigma = mean(base), pstdev(base)
    # piso no sigma evita z gigante quando a linha de base é plana
    floor = max(abs(mu) * 0.05, 1e-9)
    z = (mean(recent) - mu) / max(sigma, floor)
    slope = _slope(values)
    trend = "crescente" if slope > floor * 0.01 else "decrescente" if slope < -floor * 0.01 else "estável"
    return {
        "anomalous": abs(z) >= z_threshold,
        "z_score": round(z, 2),
        "baseline_mean": round(mu, 4),
        "recent_mean": round(mean(recent), 4),
        "max": round(max(values), 4),
        "trend": trend,
        "samples": len(values),
    }
