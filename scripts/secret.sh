#!/usr/bin/env bash
# Cria/atualiza o Secret com as credenciais lidas do .env (valores nunca são impressos).
#   CLAUDE_CODE_OAUTH_TOKEN  token da assinatura (claude setup-token)  -> backend "cli"
#   ANTHROPIC_API_KEY        chave da API paga (opcional)              -> backend "api"
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo "ERRO: .env não encontrado. Copie .env.example para .env e preencha."; exit 1; }

get() { grep -E "^$1=" .env | head -1 | cut -d= -f2- | tr -d '\r\n ' || true; }
TOKEN="$(get CLAUDE_CODE_OAUTH_TOKEN)"
KEY="$(get ANTHROPIC_API_KEY)"
[ -n "$TOKEN$KEY" ] || { echo "ERRO: defina CLAUDE_CODE_OAUTH_TOKEN ou ANTHROPIC_API_KEY no .env"; exit 1; }

kubectl create namespace aiops --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n aiops create secret generic aiops-secrets \
  --from-literal=CLAUDE_CODE_OAUTH_TOKEN="$TOKEN" \
  --from-literal=ANTHROPIC_API_KEY="$KEY" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null
echo ">> Secret aiops-secrets aplicado (token: $([ -n "$TOKEN" ] && echo sim || echo não), api key: $([ -n "$KEY" ] && echo sim || echo não))."
kubectl -n aiops rollout restart deployment/aiops-agent >/dev/null 2>&1 || true
