"""Backend que usa o Claude Code em modo headless (`claude -p`) com a assinatura.

Usa a CLI oficial com o token de longa duração gerado por `claude setup-token`. O token é
repassado somente à CLI; o agente nunca o usa para chamar a API diretamente.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile

from . import evidence
from .agent_prompt import SYSTEM_PROMPT
from .config import CLAUDE_CODE_OAUTH_TOKEN, CLI_MODEL, CLI_TIMEOUT_SECONDS, CONFIG_DIR

_REQUIRED = ["resumo", "tipo", "severidade", "causa_provavel", "evidencias", "acao_sugerida", "confianca"]
# Esta chamada é só raciocínio sobre evidências já coletadas: nenhuma ferramenta é necessária
_DENY = "Bash,Edit,Write,Read,NotebookEdit,WebFetch,WebSearch,Glob,Grep,Task,Agent"


def _schema_arg() -> str:
    raw = (CONFIG_DIR / "incident.schema.json").read_text(encoding="utf-8")
    schema = json.loads(raw)
    schema.pop("$schema", None)  # a CLI não resolve o meta-schema draft 2020-12
    schema.pop("title", None)
    return json.dumps(schema, ensure_ascii=False)


def diagnose(alert: dict, meta: dict) -> dict:
    prompt = (
        f"{SYSTEM_PROMPT}\n"
        "Contexto: as evidências abaixo já foram coletadas para você. Não há ferramentas; "
        "raciocine apenas sobre elas e cite a fonte (nome da seção) em cada evidência.\n\n"
        f"{evidence.collect(alert)}\n\n"
        "Produza o diagnóstico final conforme o schema JSON."
    )
    # ANTHROPIC_API_KEY fora do ambiente: com ela a CLI usaria a API paga em vez da assinatura
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", "/home/agent"),
        "CLAUDE_CODE_OAUTH_TOKEN": CLAUDE_CODE_OAUTH_TOKEN,
    }
    proc = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "json", "--json-schema", _schema_arg(),
         "--no-session-persistence", "--model", CLI_MODEL, "--disallowedTools", _DENY],
        capture_output=True, text=True, timeout=CLI_TIMEOUT_SECONDS, env=env,
        stdin=subprocess.DEVNULL, cwd=tempfile.gettempdir(),
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude cli saiu com {proc.returncode}: {(proc.stderr or proc.stdout)[:300]}")

    out = json.loads(proc.stdout)
    if out.get("is_error"):
        raise RuntimeError(f"claude cli retornou erro: {str(out.get('result'))[:300]}")

    diag = out.get("structured_output")
    if not isinstance(diag, dict):
        text = str(out.get("result", ""))
        m = re.search(r"\{.*\}", text, re.S)
        diag = json.loads(m.group(0)) if m else None
    if not isinstance(diag, dict) or any(k not in diag for k in _REQUIRED):
        raise RuntimeError("saída da CLI fora do schema")

    usage = out.get("usage", {})
    meta["model"] = next(iter(out.get("modelUsage", {})), CLI_MODEL)
    meta["turns"] = out.get("num_turns", 1)
    meta["input_tokens"] = usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0) \
        + usage.get("cache_read_input_tokens", 0)
    meta["output_tokens"] = usage.get("output_tokens", 0)
    meta["tools"] = ["evidence.collect"]
    return diag
