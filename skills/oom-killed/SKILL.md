---
name: oom-killed
description: Investigar containers encerrados por falta de memória (OOMKilled, exit code 137).
---

# OOMKilled

## Confirmar
- `lastState.terminated.reason == OOMKilled` e `exitCode == 137`.
- Evento `OOMKilling` no node, se disponível.

## Investigar
1. Compare uso de memória (working set) com o `limit` nos 60 min anteriores.
2. Crescimento linear contínuo sugere vazamento; salto abrupto sugere pico de carga.
3. Verifique se o limit é baixo para a carga normal (uso médio próximo de 80–100% do limit).
4. Verifique mudanças recentes de deploy/versão.

## Diagnóstico típico
- Limit abaixo da necessidade → aumentar limit/request.
- Vazamento → investigar a aplicação; aumentar limit é apenas paliativo.

## Ação sugerida
Indicar o novo limit com margem (ex.: pico observado + 30%) e recomendar análise de heap se houver crescimento contínuo.
