"""Redação de segredos: nada sensível deve sair do cluster em direção à API."""
import re

_PATTERNS = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}"), "Bearer [REDACTED]"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"), "[REDACTED_JWT]"),
    # chave=valor / chave: valor para nomes sensíveis
    (
        re.compile(r"(?i)\b([A-Za-z0-9_\-]*(?:password|passwd|secret|token|api[_\-]?key|private[_\-]?key)[A-Za-z0-9_\-]*)\s*([=:])\s*\S+"),
        r"\1\2[REDACTED]",
    ),
    # credenciais embutidas em URL: scheme://user:pass@host
    (re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://)[^\s:/@]+:[^\s@]+@"), r"\1[REDACTED]@"),
]


def redact(text: str) -> str:
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text
