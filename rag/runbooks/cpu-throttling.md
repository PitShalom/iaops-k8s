# Runbook: CPU throttling

## Sintomas
Latência alta ou processamento lento, porém o pod aparece Running e Ready. Nenhum erro nos
logs. A métrica `container_cpu_cfs_throttled_periods_total` cresce.

## Diagnóstico
Calcule a razão entre períodos throttled e períodos totais. Acima de 25% o impacto já é perceptível;
acima de 50% é severo. Uso de CPU colado no limit de forma sustentada indica saturação real.
Throttling com uso médio baixo indica rajadas curtas contra um limit apertado.

## Mitigação
Elevar o limit de CPU com base no p95 observado, ou remover o limit mantendo request adequado.
Para carga variável, habilitar HPA com alvo de CPU em vez de depender de um único pod grande.

## Prevenção
Dimensionar request pela média e acompanhar throttling como SLI. Evitar limits de CPU muito
próximos do request em serviços sensíveis a latência.
