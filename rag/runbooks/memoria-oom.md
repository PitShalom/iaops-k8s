# Runbook: falta de memória (OOMKilled)

## Sintomas
Pod reinicia com `exitCode 137` e `reason: OOMKilled`. O estado alterna entre Running e
CrashLoopBackOff. Memória (working set) encosta no limit antes de cada reinício.

## Diagnóstico
Compare `container_memory_working_set_bytes` com o limit. Crescimento linear contínuo indica
vazamento de memória; salto abrupto indica pico de carga ou alocação grande. Se o uso médio
já fica perto do limit, o limit está subdimensionado para a carga normal.

## Mitigação
Aumentar o limit e o request de memória com margem (pico observado mais 30%). Aumentar o limit
é paliativo quando há vazamento: abrir investigação de heap/profiling na aplicação.

## Prevenção
Definir request igual ao uso típico e limit com margem. Monitorar tendência de memória, não só
o valor absoluto, e alertar em crescimento contínuo.
