# Guia de aprendizado do laboratório

Este guia acompanha a construção do projeto. Cada seção explica **o conceito**, mostra
**onde ele aparece no lab** e propõe um **exercício** para você rodar.

> Dica: abra um terminal WSL (`wsl`) e rode os comandos de lá. Para não digitar o contexto
> toda hora: `kubectl config use-context kind-iaops`.

## 1. As camadas do laboratório

| Camada | O que é | Onde está no lab |
|---|---|---|
| Docker | Roda containers | Base de tudo |
| Kind | Kubernetes dentro de containers Docker | `k8s/kind-config.yaml` |
| Kubernetes | Orquestra pods, deployments, services | namespaces `monitoring`, `demo`, `aiops` |
| Prometheus | Coleta e armazena métricas (séries temporais) | pod `prometheus-kps-prometheus-0` |
| kube-state-metrics | Transforma o *estado* do K8s em métricas | `kube_pod_container_status_*` |
| Alertmanager | Agrupa, deduplica e roteia alertas | `k8s/monitoring/values.yaml` |
| Grafana | Visualização | http://localhost:3000 |
| Agente (a construir) | Investiga e diagnostica com Claude | `src/`, `agents/`, `skills/` |

## 2. O caminho de um alerta (o que acabamos de ver funcionando)

```
pod estoura memória
  → o kernel mata o processo (exit code 137)
  → o kubelet registra lastState.terminated.reason = OOMKilled
  → kube-state-metrics expõe kube_pod_container_status_last_terminated_reason{reason="OOMKilled"} = 1
  → Prometheus avalia a regra DemoPodOOMKilled a cada 15s → alerta "firing"
  → Alertmanager recebe, agrupa por (alertname, namespace, pod) e espera group_wait (10s)
  → envia webhook para o aiops-agent  ← é aqui que a IA entra
```

**Conceito-chave:** o alerta não vem do pod. Vem de uma *métrica sobre o estado do pod*,
avaliada por uma regra PromQL. Por isso cada etapa pode falhar de um jeito diferente.

## 3. Lendo uma regra PromQL (de `k8s/monitoring/rules.yaml`)

```promql
increase(kube_pod_container_status_restarts_total{namespace="demo"}[5m]) > 0
and on (namespace, pod, container)
kube_pod_container_status_last_terminated_reason{namespace="demo", reason="OOMKilled"} == 1
```

- `increase(x[5m])`: quanto o contador subiu nos últimos 5 min.
- `> 0`: filtra só o que reiniciou. Em PromQL, comparação **filtra** séries, não retorna true/false.
- `and on (...)`: só mantém as séries que existem dos dois lados com os mesmos labels.
- Resultado: "reiniciou recentemente **e** a última morte foi OOM".

`for: 1m` significa que a condição precisa se manter por 1 min antes de virar `firing`.
Enquanto isso o alerta fica `pending`. É por isso que o `DemoPodCrashLooping` demorou.

## 4. Por que os três cenários se comportam diferente

| Cenário | Causa | Sinal observável |
|---|---|---|
| `oom` | `--vm-bytes 200M` com `limit` de 64Mi | `exitCode 137`, reason `OOMKilled` |
| `crashloop` | script sai com `exit 1` | reason `Error`, depois `CrashLoopBackOff` |
| `cpu` | 2 threads com `limit` de 200m | pod `Running`, mas throttled: **nenhum erro visível** |

O caso `cpu` é o mais instrutivo: o pod está "saudável" para o Kubernetes. Só a métrica
`container_cpu_cfs_throttled_periods_total` revela o problema. É exatamente o tipo de
situação em que olhar só `kubectl get pods` engana.

## 5. Exercícios

1. **Ver o estado do pod que morreu por OOM**
   `kubectl get pod -n demo -l app=payments-api -o jsonpath='{.items[0].status.containerStatuses[0].lastState}'`
   Procure `exitCode` e `reason`.
2. **Ler o log do container anterior** (é onde fica a causa em CrashLoop)
   `kubectl logs -n demo -l app=orders-worker --previous`
3. **Eventos do namespace**, a linha do tempo do que o kubelet fez
   `kubectl get events -n demo --sort-by=.lastTimestamp`
4. **Mexer na causa**: edite `k8s/chaos/oom.yaml`, suba o `limit` de memória para `256Mi`,
   rode `kubectl apply -f k8s/chaos/oom.yaml` e observe o alerta resolver.
5. **Grafana**: em *Explore*, rode a query `kube_pod_container_status_restarts_total{namespace="demo"}`
   e veja os restarts subindo em escada.

## 6. Perguntas para fixar

- Por que o Alertmanager existe separado do Prometheus?
- O que acontece se o webhook do agente estiver fora do ar? (O lab está assim agora: veja os
  logs do Alertmanager.)
- Por que `OOMKilled` e `CrashLoopBackOff` são coisas diferentes, e por que um leva ao outro?

## 7. Glossário rápido

- **Pod**: menor unidade executável do K8s (um ou mais containers).
- **Deployment**: mantém N réplicas de um pod e reinicia se morrer.
- **limit / request**: teto e reserva de recurso. Passar do limit de memória = OOM; passar do de CPU = throttling.
- **Label**: par chave/valor que identifica séries e objetos, e é a base de agrupar e filtrar.
- **Fingerprint**: identidade de um incidente (`namespace/workload/alertname`), usada pela memória do agente.
