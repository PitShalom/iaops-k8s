#!/usr/bin/env bash
# Sobe o laboratório: cluster Kind + stack de monitoramento + regras de alerta.
set -euo pipefail
cd "$(dirname "$0")/.."

CLUSTER=iaops

for bin in docker kind kubectl helm; do
  command -v "$bin" >/dev/null 2>&1 || { echo "ERRO: '$bin' não encontrado. Veja a seção Pré-requisitos do README."; exit 1; }
done
docker info >/dev/null 2>&1 || { echo "ERRO: o daemon do Docker não está acessível."; exit 1; }

if kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  echo ">> Cluster '$CLUSTER' já existe, reutilizando."
else
  echo ">> Criando cluster Kind '$CLUSTER'..."
  kind create cluster --config k8s/kind-config.yaml
fi
kubectl config use-context "kind-$CLUSTER" >/dev/null

echo ">> Instalando kube-prometheus-stack..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update >/dev/null
helm upgrade --install kps prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --values k8s/monitoring/values.yaml \
  --wait --timeout 10m

echo ">> Aplicando regras de alerta e namespace demo..."
kubectl apply -f k8s/monitoring/rules.yaml
kubectl apply -f k8s/chaos/namespace.yaml

cat <<EOF

Laboratório no ar.
  Grafana : http://localhost:3000   (admin / iaops-lab)
  Próximo : make agent   (build + deploy do agente)
            make chaos SCENARIO=oom
EOF
