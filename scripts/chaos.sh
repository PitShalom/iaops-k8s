#!/usr/bin/env bash
# Injeta ou remove um cenário de falha no namespace demo.
# Uso: scripts/chaos.sh <oom|crashloop|cpu|all|clean>
set -euo pipefail
cd "$(dirname "$0")/.."

scenario="${1:-}"
case "$scenario" in
  oom|crashloop|cpu)
    kubectl apply -f k8s/chaos/namespace.yaml
    kubectl apply -f "k8s/chaos/${scenario}.yaml"
    echo "Cenário '${scenario}' aplicado. Acompanhe: kubectl get pods -n demo -w"
    ;;
  all)
    kubectl apply -f k8s/chaos/namespace.yaml
    kubectl apply -f k8s/chaos/oom.yaml -f k8s/chaos/crashloop.yaml -f k8s/chaos/cpu.yaml
    ;;
  clean)
    kubectl delete -f k8s/chaos/oom.yaml -f k8s/chaos/crashloop.yaml -f k8s/chaos/cpu.yaml --ignore-not-found
    ;;
  *)
    echo "Uso: $0 <oom|crashloop|cpu|all|clean>"
    exit 1
    ;;
esac
