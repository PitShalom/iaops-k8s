.PHONY: up down chaos clean-chaos agent secret status

SCENARIO ?= oom

up:            ## Sobe cluster Kind + kube-prometheus-stack + regras
	bash scripts/up.sh

down:          ## Destrói o cluster
	bash scripts/down.sh

chaos:         ## Injeta falha: make chaos SCENARIO=oom|crashloop|cpu|all
	bash scripts/chaos.sh $(SCENARIO)

clean-chaos:   ## Remove os cenários de falha
	bash scripts/chaos.sh clean

agent:         ## Build + deploy do agente no Kind
	bash scripts/agent.sh

secret:        ## Injeta ANTHROPIC_API_KEY (do .env) como Secret no cluster
	bash scripts/secret.sh

status:        ## Visão rápida do laboratório
	kubectl get pods -A | grep -E "NAMESPACE|monitoring|demo|aiops"
