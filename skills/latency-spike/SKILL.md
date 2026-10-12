---
name: latency-spike
description: Investigar aumento de latência ou taxa de erro em um serviço.
---

# Latency Spike

## Investigar
1. Marque o horário de início do desvio na latência/erros.
2. Correlacione com: deploy/rollout, CPU/throttling, memória, restarts, dependências.
3. Verifique se afeta todas as réplicas ou só algumas (pod ruim específico).
4. Verifique saturação de recursos no node.

## Ação sugerida
Indicar o evento correlacionado mais próximo no tempo e a mitigação correspondente (rollback, escala, ajuste de recursos).
