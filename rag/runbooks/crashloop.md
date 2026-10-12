# Runbook: CrashLoopBackOff

## Sintomas
Pod em `CrashLoopBackOff`, restarts crescentes, intervalo entre tentativas aumentando
(10s, 20s, 40s... até 5 min). Pod nunca fica Ready.

## Diagnóstico
A causa quase sempre está no log do container anterior (`kubectl logs --previous`). Verifique o
exitCode: 1 ou 2 indica erro da aplicação, 137 indica OOM ou kill, 139 indica falha de segmentação,
143 indica SIGTERM. Procure variável de ambiente ausente, Secret ou ConfigMap inexistente,
dependência indisponível (banco, fila) e probes de liveness agressivas demais.

## Mitigação
Corrigir a configuração apontada pelo erro e reaplicar o deployment. Se a causa for uma mudança
recente, avaliar rollback com `kubectl rollout undo`.

## Prevenção
Validar configuração obrigatória no start com mensagem clara, usar readiness probe e init
containers para dependências, e revisar manifests em CI antes do deploy.
