---
name: report-format
description: Template e tom do diagnóstico final de incidente.
---

# Formato do relatório

Tom: conciso, técnico, factual. Sem especulação sem rótulo de incerteza.

```
# Incidente: <alertname> — <namespace>/<workload>
Severidade: <baixa|media|alta|critica>   Confiança: <0-1>   Recorrência: <n>

## Resumo
<até 2 frases>

## Causa provável
<explicação objetiva>

## Evidências
- [<fonte>] <detalhe>

## Ação sugerida
<passos para um humano executar>

## Referências
- <runbook#seção>
```

Regras: toda afirmação com evidência citada; ação sempre como recomendação.
