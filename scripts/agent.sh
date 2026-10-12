#!/usr/bin/env bash
# Build da imagem do agente, carga no Kind e deploy.
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE=aiops-agent:dev
CLUSTER=iaops

echo ">> Build da imagem $IMAGE..."
docker build -t "$IMAGE" .

echo ">> Carregando imagem no cluster Kind..."
kind load docker-image "$IMAGE" --name "$CLUSTER"

echo ">> Aplicando manifests..."
kubectl apply -f k8s/aiops/agent.yaml
# Recria o pod para pegar a imagem nova (a tag :dev não muda)
kubectl -n aiops rollout restart deployment/aiops-agent
kubectl -n aiops rollout status deployment/aiops-agent --timeout=180s

echo ">> Agente no ar: http://localhost:8080/healthz"
