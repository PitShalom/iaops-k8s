---
name: crashloop
description: Investigar pods em CrashLoopBackOff ou com restarts repetidos.
---

# CrashLoopBackOff

## Investigar, nesta ordem
1. Logs do container anterior (`previous`) — a causa costuma estar no final.
2. `exitCode`: 1/2 erro de aplicação; 137 OOM/kill; 139 segfault; 143 SIGTERM.
3. Probes (liveness/readiness) com timeout ou caminho inválido.
4. ConfigMap/Secret/variável de ambiente ausente ou inválida.
5. Dependência indisponível (DB, serviço) no start.
6. Mudança recente de imagem/config.

## Ação sugerida
Apontar a evidência exata (linha de log ou evento) e a correção correspondente.
