# Runbook: triagem geral de incidentes

## Ordem de investigação
Comece pelo estado do pod (fase, restarts, último estado), depois eventos, depois logs do
container atual e do anterior, e por fim métricas da última hora. Correlacione o início do
desvio com deploys, mudanças de configuração e tráfego.

## Recorrência
Mesmo workload falhando repetidamente pelo mesmo motivo indica problema estrutural, não
transitório. Registre a causa e priorize correção definitiva em vez de reinício manual.

## Comunicação
Relatório curto: o que aconteceu, impacto, causa provável com evidência, ação recomendada e
nível de confiança. Separe fato observado de hipótese.
