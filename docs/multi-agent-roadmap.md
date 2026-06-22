# QAgent — Roadmap para Multi-Agente Autônomo

> Gerado em: 2026-05-01

---

## Definição de "Multi-Agente Autônomo"

Sistema onde agentes:
1. **Percebem** o ambiente sem intervenção humana
2. **Decidem** autonomamente qual tarefa executar
3. **Comunicam** entre si diretamente (não apenas via orquestrador externo)
4. **Aprendem** com resultados anteriores e ajustam comportamento
5. **Monitoram** saúde do sistema e se auto-reparam
6. **Escalam** tarefas para humanos apenas em exceções

---

## Estado Atual vs. Alvo

| Dimensão | Estado Atual | Alvo |
|----------|-------------|------|
| **Disparo** | `repository_dispatch` manual pelo repo-alvo | QAgent monitora repositórios autonomamente |
| **Comunicação entre agentes** | Via orquestrador Python (não direta) | Agentes trocam mensagens em runtime |
| **Planejamento de tarefas** | Determinístico (hardcoded no orchestrator) | Agente planeja dinamicamente quais steps executar |
| **Memória cross-run** | LanceDB (lições + knowledge RAG) | Memória estruturada de decisões, padrões, performance |
| **Auto-melhoria** | Não existe | Agentes avaliam própria qualidade e ajustam prompts |
| **Monitoramento** | JSON por execução | Dashboard em tempo real + alertas |
| **Escalonamento** | sys.exit(1) + PR comment | Protocolo de escalação com contexto rico |
| **Cobertura de repositórios** | Um por disparo | Fila multi-repo com priorização |
| **Agendamento** | Controlado externamente | QAgent decide quando/o que reanalisar |

---

## O que Falta — Por Categoria

---

### 1. Percepção Autônoma

**Problema:** QAgent só age quando o repositório-alvo chama `repository_dispatch`. Não monitora ativamente.

**Falta:**
- [ ] **Webhook listener persistente** — servidor FastAPI/uvicorn (infra já existe, não está ativo) recebendo eventos GitHub diretamente
- [ ] **Polling de repositórios** — job periódico que verifica PRs abertos em múltiplos repos sem aguardar disparo
- [ ] **Detecção de mudanças autônoma** — QAgent compara HEAD com último SHA analisado para decidir se deve reanalisar

**Onde implementar:**
- Ativar `FastAPI` + `uvicorn` (já em `requirements.txt`)
- Criar `src/services/webhook_listener.py` + `src/services/repo_monitor.py`
- Adicionar scheduler (ex.: APScheduler) para polling

---

### 2. Planejamento Dinâmico de Tarefas

**Problema:** Pipeline é hardcoded em `AnalysisOrchestrator` — steps executados são fixos por risco.

**Falta:**
- [ ] **Agente planejador** — recebe contexto do PR e decide quais stages executar, em que ordem, com quais parâmetros
- [ ] **Grafo de tarefas dinâmico** — em vez de pipeline linear, DAG de dependências entre tasks
- [ ] **Replanejamento mid-execution** — se um stage falha ou retorna resultado inesperado, planejar alternativa
- [ ] **Priorização de arquivos** — agente decide quais arquivos analisar primeiro baseado em risco histórico

**Onde implementar:**
- Criar `src/agent/planner_agent.py` + `src/crew/planning_crew.py`
- Substituir `AnalysisOrchestrator` por engine de DAG (ex.: Prefect, Temporal, ou implementação própria)

**Fundação implementada:** `ExecutionPlan`, Planner Agent limitado por catálogo,
runtime governado e máquina de estados JSON estão disponíveis no pipeline
pós-review por meio de `--agentic-runtime`. A expansão para geração/revisão de
testes e execução distribuída continua pendente.

---

### 3. Comunicação Direta Entre Agentes

**Problema:** Agentes não se comunicam diretamente. Dados fluem via Python objects entre crews isolados.

**Falta:**
- [ ] **Bus de mensagens inter-agente** — agentes podem publicar descobertas e outros agentes subscrevem
- [ ] **Solicitação de sub-tarefa** — agente QA pode solicitar ao agente de memória busca semântica em runtime (sem ser tool hardcoded)
- [ ] **Handoff de contexto** — quando TestGenerator recebe artefato do QA, carregar contexto completo da análise anterior sem reprocessar
- [ ] **Protocolo de desacordo** — agente crítico pode bloquear decision do QA com justificativa estruturada

**Onde implementar:**
- `CooperativeAnalysisCrewRunner` (já existe, experimental) — estabilizar e expandir
- Adicionar `CrewAI Process.hierarchical` em mais crews
- Implementar shared state store (Redis ou SQLite) para mensagens inter-crew

---

### 4. Memória Estruturada e Aprendizado

**Problema:** LanceDB armazena lições textuais de PRs. Sem memória de decisões, performance de agentes, ou padrões de repositório.

**Falta:**
- [ ] **Memória de decisões** — registrar qual analysis_mode foi escolhido, se foi correto, feedback do PR owner
- [ ] **Perfil de repositório** — acumular dados por repo: linguagem, padrões, frequência de risk levels, tipos de bugs recorrentes
- [ ] **Memória de performance de agente** — rastrear quais prompts/configurações produziram melhores resultados
- [ ] **Feedback loop de testes** — se testes gerados foram aprovados/rejeitados no PR, registrar e ajustar estratégia
- [ ] **Decay de memória** — lições antigas com baixa relevância recebem menor peso (sem isso, memória cresce ilimitadamente)

**Onde implementar:**
- Expandir `src/tools/memory_tools.py` com tipos de memória adicionais
- Criar `src/schemas/repository_profile.py`, `src/schemas/agent_performance_record.py`
- Adicionar tabelas separadas em LanceDB por tipo de memória
- Coletar feedback via reações/labels no PR gerado

---

### 5. Auto-Avaliação e Auto-Melhoria

**Problema:** Agentes não avaliam a qualidade própria da saída. Sem mecanismo de refinamento iterativo.

**Falta:**
- [ ] **Scoring de outputs** — cada saída de agente recebe score determinístico (ex.: test coverage %, severity distribution)
- [ ] **Retry inteligente** — se score abaixo de threshold, agente reformula e tenta novamente (com contexto do erro)
- [ ] **A/B de prompts** — rodar variações de prompt e registrar qual produz melhores resultados por tipo de arquivo
- [ ] **Self-critique loop** — `AnalysisCriticAgent` (já existe!) deve ser ativado sempre, não apenas no modo cooperativo
- [ ] **Calibração de risco** — comparar risk_level previsto com bugs encontrados no PR para calibrar thresholds

**Onde implementar:**
- `AnalysisCriticAgent` já existe em `src/agent/analysis_critic_agent.py` — ativar fora do modo cooperativo
- Criar `src/services/output_scorer.py`
- Adicionar campo `quality_score` em `FileAnalysisArtifact`
- Implementar retry loop em `QACrewRunner`

**Fundação implementada:** `AgenticRunEvaluator` aplica retry limitado,
correção única, conclusão e escalação humana com decisões persistidas.

---

### 6. Monitoramento e Observabilidade em Tempo Real

**Problema:** Observabilidade existe em JSON por execução mas sem agregação, alertas ou dashboard.

**Falta:**
- [ ] **Agregação de métricas** — coletar step_durations, risk_levels, fallbacks_triggered de todas as execuções
- [ ] **Dashboard** — visualização de execuções, taxa de sucesso, distribuição de risk levels, custo LLM
- [ ] **Alertas** — notificar quando fallback_rate > threshold ou quando execuções falham repetidamente
- [ ] **Rastreamento de custo LLM** — tokens consumidos por execução/repo/período
- [ ] **Health check** — endpoint `/health` que verifica conectividade LLM, LanceDB, GitHub API

**Onde implementar:**
- Criar `src/services/metrics_collector.py` que grava em SQLite ou Prometheus
- Ativar FastAPI: adicionar `src/api/routes.py` com `/health`, `/metrics`, `/runs`
- Integrar com Grafana ou criar dashboard simples em HTML (scripts já geram site)

---

### 7. Gestão de Múltiplos Repositórios

**Problema:** QAgent opera em um repositório por execução. Sem coordenação multi-repo.

**Falta:**
- [ ] **Registro de repositórios** — lista de repos monitorados com configuração por repo
- [ ] **Fila de trabalho** — múltiplos PRs de múltiplos repos em fila com priorização
- [ ] **Isolamento de contexto** — garantir que análise do repo A não contamine contexto do repo B
- [ ] **Limites de taxa por repo** — evitar consumo excessivo de LLM para repos de baixa prioridade
- [ ] **Configuração por repo** — `.qagent/config.yml` no repo-alvo define qual análise QAgent deve fazer

**Onde implementar:**
- Criar `src/services/repo_registry.py` + `src/services/work_queue.py`
- Substituir disparo único por worker loop que consome fila
- Expandir `.qagent/knowledge/` para incluir `.qagent/config.yml`

---

### 8. Protocolo de Escalação para Humanos

**Problema:** Escalação atual = `sys.exit(1)` + comentário no PR. Sem contexto estruturado nem tracking.

**Falta:**
- [ ] **Escalação rica** — ao escalar, incluir: risk_level, findings resumidos, confiança do agente, ação recomendada
- [ ] **Tipos de escalação** — BLOCK (não mergear), REVIEW (humano revise), INFORM (FYI)
- [ ] **Tracking de escalações** — registrar escalações não resolvidas, reagendar análise após resolução
- [ ] **SLA de resposta** — se humano não responde em N dias, QAgent pode tomar ação padrão
- [ ] **Labels automáticos** — aplicar labels GitHub baseados em análise (ex.: `high-risk`, `needs-test-coverage`)

**Onde implementar:**
- Expandir `src/utils/review_comment_utils.py` com templates de escalação estruturada
- Criar `src/services/escalation_manager.py`
- Usar GitHub Labels API via PyGithub

---

### 9. Configuração Dinâmica e Self-Configuration

**Problema:** Configurações hardcoded em `settings.py` e `TokenBudgetPlanner`. Sem ajuste dinâmico.

**Falta:**
- [ ] **Config por repositório** — `.qagent/config.yml` permite repo customizar thresholds, agentes ativos, LLM preferido
- [ ] **Ajuste dinâmico de temperatura** — agentes mais críticos usam temperatura mais baixa automaticamente
- [ ] **Seleção dinâmica de modelo** — usar modelo maior para arquivos HIGH-risk, menor para LOW
- [ ] **Budget adaptativo** — se API Groq está lenta, reduzir chamadas automaticamente

**Onde implementar:**
- Criar `src/config/repo_config_loader.py`
- Expandir `Settings` para suportar overrides por arquivo/repo
- Adicionar `model_selector` em `TokenBudgetPlanner`

---

### 10. Testes e Confiabilidade do QAgent Próprio

**Problema:** Testes unitários existem (`tests/`) mas sem testes de integração ponta-a-ponta do próprio pipeline.

**Falta:**
- [ ] **Testes de integração** — executar pipeline completo contra PR sintético e validar saída
- [ ] **Fixtures de PR** — conjunto de PRs de teste com risco conhecido para validar classificação
- [ ] **Contrato de API LLM mockado** — testes não dependem de API real
- [ ] **Regression suite** — garantir que mudanças em prompts não degradam qualidade de análise
- [ ] **Load testing** — verificar comportamento com múltiplos PRs simultâneos

---

## Priorização Sugerida

### Fase 1 — Fundação Autônoma (Alto Impacto, Baixo Esforço)
1. **Ativar AnalysisCriticAgent** em modo padrão (agente já existe, só ativar fora do cooperativo)
2. **Perfil de repositório** em LanceDB (acumular dados por repo entre execuções)
3. **Feedback loop de testes** (registrar se PR de testes foi aprovado/rejeitado)
4. **Health check endpoint** via FastAPI (infra já disponível)
5. **Labels automáticos** via GitHub API (PyGithub já integrado)

### Fase 2 — Comunicação e Planejamento
1. **Estabilizar CooperativeAnalysisCrewRunner** (já existe, só está experimental)
2. **Agente planejador** que decide dinamicamente quais stages executar
3. **Webhook listener** via FastAPI para receber eventos sem `repository_dispatch`
4. **Fila de trabalho** para múltiplos repositórios

### Fase 3 — Autonomia Completa
1. **Monitoramento de repos** sem disparo externo
2. **Auto-melhoria de prompts** via scoring de outputs
3. **Dashboard de métricas** com Grafana ou site gerado
4. **Self-configuration** via `.qagent/config.yml` no repo-alvo
5. **Protocolo de escalação estruturado** com SLA e tracking

---

## Dependências Técnicas Novas (Estimadas)

| Componente | Biblioteca Sugerida | Justificativa |
|------------|--------------------|-|
| Scheduler/Polling | `APScheduler` ou `rq` | Jobs periódicos sem cron externo |
| Work queue | `rq` (Redis) ou `sqlite-queue` | Fila multi-repo com priorização |
| Métricas | `prometheus-client` | Padrão para coleta; Grafana integra |
| State store inter-agente | `redis` ou `sqlite3` (stdlib) | Mensagens entre crews |
| Config por repo | Apenas `PyYAML` | Leitura de `.qagent/config.yml` |

---

## Resumo das Lacunas Críticas

```
QAgent hoje:
  ✅ Pipeline QA end-to-end funcional
  ✅ Memória vetorial (lições de PRs)
  ✅ Auto-fix de testes
  ✅ Contratos tipados
  ✅ Fallback determinístico
  ✅ RAG por projeto

QAgent autônomo precisa de:
  ❌ Percepção autônoma (sem repository_dispatch)
  ❌ Planejamento dinâmico de tarefas
  ❌ Comunicação direta entre agentes em runtime
  ❌ Memória de decisões e performance
  ❌ Auto-avaliação e scoring de outputs
  ❌ Monitoramento agregado e alertas
  ❌ Coordenação multi-repositório
  ❌ Escalação estruturada com tracking
  ❌ Configuração dinâmica por repositório
  ❌ Testes de integração do próprio pipeline
```
