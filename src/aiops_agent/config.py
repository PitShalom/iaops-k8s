"""Configuração do agente, lida de variáveis de ambiente."""
import os
from pathlib import Path

# Raiz do app: /app na imagem, raiz do repo em desenvolvimento
APP_DIR = Path(os.getenv("APP_DIR", Path(__file__).resolve().parents[2]))
SKILLS_DIR = APP_DIR / "skills"
RUNBOOKS_DIR = APP_DIR / "rag" / "runbooks"
CONFIG_DIR = APP_DIR / "config"

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", str(DATA_DIR / "reports")))

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://kps-prometheus.monitoring.svc.cluster.local:9090")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
MODEL = os.getenv("AIOPS_MODEL", "claude-sonnet-5-5")

# Backend "cli": usa o Claude Code em modo headless com a assinatura (token de `claude setup-token`)
CLAUDE_CODE_OAUTH_TOKEN = os.getenv("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
CLI_MODEL = os.getenv("AIOPS_CLI_MODEL", "sonnet")
CLI_TIMEOUT_SECONDS = int(os.getenv("AIOPS_CLI_TIMEOUT", "150"))
# auto = tenta cli (se houver token), depois api (se houver chave), depois regras
LLM_BACKEND = os.getenv("AIOPS_LLM_BACKEND", "auto")

# Somente alertas destes namespaces viram incidentes (evita ruído do próprio monitoramento)
WATCH_NAMESPACES = {n.strip() for n in os.getenv("WATCH_NAMESPACES", "demo").split(",") if n.strip()}

# Limites (ver config/limits.yaml)
MAX_TURNS = int(os.getenv("MAX_TURNS", "12"))
MAX_TOKENS_INCIDENT = int(os.getenv("MAX_TOKENS_INCIDENT", "40000"))
LOG_TAIL_LINES = int(os.getenv("LOG_TAIL_LINES", "100"))
DEDUPE_WINDOW_SECONDS = int(os.getenv("DEDUPE_WINDOW_SECONDS", "300"))
TOOL_RESULT_MAX_CHARS = int(os.getenv("TOOL_RESULT_MAX_CHARS", "6000"))
