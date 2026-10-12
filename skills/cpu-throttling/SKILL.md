---
name: cpu-throttling
description: Investigar alta CPU, throttling e saturação de workloads.
---

# CPU / Throttling

## Investigar
1. Compare uso de CPU com `limit` e `request`.
2. Verifique `container_cpu_cfs_throttled_periods_total / container_cpu_cfs_periods_total`.
3. Throttling alto com uso abaixo do node indica limit apertado.
4. Uso próximo ao limit sustentado indica saturação real: considerar HPA ou mais réplicas.
5. Correlacione com aumento de tráfego ou deploy recente.

## Ação sugerida
Ajustar limit/request com base no p95 observado, ou habilitar HPA com alvo de CPU.
