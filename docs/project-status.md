# QAgent — Status Atual do Projeto

> Gerado em: 2026-05-01

---

## Visão Geral

QAgent é um sistema de QA automatizado baseado em agentes de IA que analisa pull requests, gera testes, revisa código gerado e persiste aprendizados em memória vetorial. Opera como pipeline externo disparado por repositórios-alvo via GitHub Actions.

---

## Arquitetura Geral

```
Repositório-alvo (push/PR)
        │
        ▼
[GitHub Actions: qa-agent.yml]
        │
  ┌─────┴──────────────────────────────────────┐
  │                                            │
  ▼                                            │
[STAGE 1: QA Analysis]                         │
  src/main.py                                  │
  ├─ TokenBudgetPlanner → skip/standard/coop   │
  ├─ QACrewRunner ou CooperativeCrewRunner      │
  ├─ AnalysisOrchestrator                      │
  │   ├─ evaluate_risk()                       │
  │   ├─ build_strategy()                      │
  │   ├─ enrich_high_risk() [LLM, se HIGH]     │
  │   └─ evaluate_final()                      │
  └─ export_artifacts_to_json()               │
        │                                     │
        ▼                                     │
[STAGE 2: Test Generation]                    │
  src/main_test_generator.py                  │
  ├─ Carrega e atualiza artifacts.json         │
  ├─ TestGeneratorCrewRunner                  │
  ├─ parse_test_files_from_output()           │
  └─ create PR com testes gerados             │
        │                                     │
        ▼                                     │
[STAGE 3: Test Review]                        │
  src/main_test_reviewer.py                   │
  ├─ TestReviewerCrewRunner                   │
  ├─ TestExecutionRunner (pytest)             │
  ├─ TestFixerCrewRunner (auto-fix)           │
  └─ Posta resultado no PR                   │
        │
        ▼
[STAGE 4: Memory Ingestion] (async)
  .github/scripts/ingest_comment.py
  └─ MemoryCrewRunner → LanceDB
```

---

## Componentes Implementados

### Agentes (8)

| Agente | Papel | Status |
|--------|-------|--------|
| `QAAgentFactory` | Investigador QA sênior — analisa diffs | ✅ Estável |
| `HighRiskStrategyAgentFactory` | Especialista em estratégia para arquivos HIGH | ✅ Estável |
| `TestGeneratorAgentFactory` | Gera código de teste executável | ✅ Estável |
| `TestReviewerAgentFactory` | Revisa qualidade dos testes gerados | ✅ Estável |
| `TestFixerAgentFactory` | Auto-corrige testes falhos | ✅ Estável |
| `MemoryAgentFactory` | Extrai lições de comentários de PR | ✅ Estável |
| `CooperativeManagerAgentFactory` | Gerencia crew hierárquico (experimental) | ⚠️ Experimental |
| `AnalysisCriticAgentFactory` | Valida qualidade de análise (experimental) | ⚠️ Experimental |

### Crews (7)

| Crew | Propósito | Status |
|------|-----------|--------|
| `QACrewRunner` | Análise QA principal | ✅ Estável |
| `CooperativeAnalysisCrewRunner` | Crew hierárquico multi-agente | ⚠️ Experimental |
| `HighRiskTestStrategyRunner` | Enriquecimento de estratégia HIGH-risk | ✅ Estável |
| `TestGeneratorCrewRunner` | Geração de testes | ✅ Estável |
| `TestReviewerCrewRunner` | Revisão de testes gerados | ✅ Estável |
| `TestFixerCrewRunner` | Correção automática de testes | ✅ Estável |
| `MemoryCrewRunner` | Extração e persistência de lições | ✅ Estável |

### Serviços (10)

| Serviço | Propósito | Tipo |
|---------|-----------|------|
| `AnalysisOrchestrator` | Coordena pipeline pós-QA | Orquestração |
| `GovernedAgenticRuntime` | Executa planos tipados com persistência e políticas | Orquestração |
| `AgenticRunEvaluator` | Decide retry, correção, conclusão ou escalação | Determinístico |
| `JsonRunStateStore` | Persiste estado e snapshot por execução | Infraestrutura |
| `TestLifecycleCapabilityExecutor` | Gera, escreve, executa, revisa e corrige testes localmente | Orquestração |
| `TokenBudgetPlanner` | Decide modo de análise pré-LLM | Determinístico |
| `ArtifactEvaluator` | Classifica risco e qualidade | Determinístico |
| `RepoContextBuilder` | Extrai contexto do repositório | Determinístico |
| `TestStrategyBuilder` | Gera estratégia adaptativa por risco | Determinístico |
| `ArtifactExporter` | Exporta artefatos para JSON | Utilitário |
| `CIFailureCollector` | Coleta contexto de falhas CI | Utilitário |
| `TestExecutionRunner` | Wrapper pytest | Utilitário |
| `ProjectKnowledgeIndexer` | RAG: indexa `.qagent/knowledge/` | Vetorial |
| `LLMClient` | Wrapper de cliente LLM | Infraestrutura |

### Schemas Pydantic (9)

| Schema | Propósito |
|--------|-----------|
| `FileAnalysisArtifact` | Artefato central consolidado (toda a análise) |
| `TokenBudgetPlan` | Plano de orçamento de tokens |
| `ContextResult` | Contexto do repositório |
| `ReviewResult` | Resultado da análise QA |
| `TestStrategyResult` | Estratégia de testes recomendada |
| `CICheckResult` | Contexto de falhas CI |
| `TestExecutionResult` | Resultado de execução pytest |
| `GeneratedTestsReviewResult` | Revisão dos testes gerados |

### Ferramentas para Agentes (5)

| Ferramenta | Propósito |
|-----------|-----------|
| `QueryMemoriesTool` | Busca semântica em LanceDB |
| `SaveLessonTool` | Persiste lição em LanceDB |
| `ReadFileTool` | Lê arquivo do repositório |
| `SearchInRepoTool` | Grep no repositório |
| `ListFilesInRepoTool` | Lista arquivos do repositório |
| `FindRelatedTestFilesTool` | Encontra arquivos de teste relacionados |

---

## Stack Tecnológica

| Tecnologia | Versão | Uso |
|-----------|--------|-----|
| Python | 3.13 | Runtime |
| CrewAI | 1.14.3 | Orquestração de agentes |
| Pydantic | 2.11.9 | Contratos de dados |
| LanceDB | 0.30.0 | Banco de dados vetorial (memórias) |
| sentence-transformers | 5.4.1 | Embeddings (`all-MiniLM-L6-v2`, 384-dim) |
| PyGithub | 2.9.1 | API GitHub (PRs, branches, status) |
| OpenAI SDK | 2.24.0 | Cliente LLM (compatível Groq) |
| pytest | 9.0.3 | Framework de testes |
| FastAPI / Uvicorn | 0.136.1 / 0.46.0 | Disponível (não usado ativamente) |

**LLM padrão:** `groq/llama-3.3-70b-versatile` via API Groq

---

## Pipelines CI/CD

### `ci-qagent.yml` — Testes Internos
- **Trigger:** push/PR para `main`, dispatch manual
- **Ações:** Setup Python 3.13 → instalar deps → validar imports → pytest

### `qa-agent.yml` — Pipeline Principal QA
- **Trigger:** `repository_dispatch: analyze_target_repo` | dispatch manual
- **Stages:** QA Analysis → Test Generation → Test Review → Site Generation (gh-pages)

### `ingest-pr-comment.yml` — Ingestão de Memórias
- **Trigger:** `repository_dispatch: pr_comment_created`
- **Ação:** Extrai lição → embeds → persiste em LanceDB → commit no main

---

## Fluxo de Dados

```
PR diff (git)
    │
    ▼
TokenBudgetPlan ──────────────────────────────┐
{mode, context_level, include_full_file, ...}  │
    │                                          │
    ▼                                          │
ContextResult (deps, related files, convs)    │
    │                                          │
    ▼                                          │
ReviewResult (findings, test_needs)            │
    │                                     [skip]
    ▼                                          │
risk_level (LOW/MEDIUM/HIGH) ◄─────────────────┘
    │
    ▼
TestStrategyResult (recommended_tests)
    │
    ├─── [HIGH] ──► HighRiskAgent → enriched strategy
    │
    ▼
FileAnalysisArtifact (consolidado)
    │
    ├─► artifacts.json (para TestGenerator)
    └─► run_summary.json (observabilidade)
```

O `ReviewResult` é solicitado diretamente como saída Pydantic tanto no fluxo
QA padrão quanto na consolidação cooperativa. O relatório Markdown é renderizado
a partir desse contrato. O parser heurístico permanece apenas como fallback
observável para respostas incompatíveis.

### Avaliação de Risco (Determinístico)

| Severidade de Findings | Risco |
|------------------------|-------|
| Qualquer ERROR | HIGH |
| Qualquer WARN (sem ERROR) | MEDIUM |
| Apenas INFO | LOW |

### Orçamento de Tokens

| Condição | Decisão |
|---------|---------|
| Extension trivial + diff < 80 linhas | `skip` |
| `--cooperative-analysis` + não trivial | `cooperative` |
| Default | `standard` |
| Arquivo > 12K chars | `include_full_file=false` |

---

## Sistema de Memória

- **Fonte:** Comentários de PR review no repositório-alvo
- **Armazenamento:** LanceDB (vetorial, `all-MiniLM-L6-v2`)
- **RAG adicional:** `.qagent/knowledge/` no repositório-alvo (indexado por execução)
- **Uso:** Agentes consultam memórias antes de analisar arquivos HIGH-risk

---

## Observabilidade (por Artefato)

Cada `FileAnalysisArtifact` registra:
- `executed_steps` — passos executados
- `skipped_steps` — passos pulados + razões
- `applied_policies` — políticas ativas (ex.: `strategy_HIGH`, `token_budget_skip`)
- `fallbacks_triggered` — fallbacks ativados
- `step_durations_ms` — timing por passo
- `diagnostic_notes` — notas de decisão
- `qa_structured_output` em `applied_policies` quando o contrato direto foi usado
- `qa_markdown_parser` em `fallbacks_triggered` quando houve fallback legado
- `execution_plan`, `agentic_run_id`, `agentic_run_status` e decisões do evaluator
- `agentic_run_history` preserva execuções anteriores entre análise e testes

---

## Pontos Fortes Atuais

1. **Pipeline end-to-end funcional:** QA → TestGen → TestReview em 3 stages GitHub Actions
2. **Fallback determinístico:** falha de LLM nunca para o pipeline
3. **Contratos tipados:** todos os dados fluem via Pydantic schemas
4. **Orçamento de tokens:** decisão pré-LLM evita chamadas desnecessárias
5. **Memória persistente:** lições acumulam via LanceDB entre execuções
6. **Auto-fix de testes:** TestFixerAgent corrige falhas sem intervenção humana
7. **RAG por projeto:** `.qagent/knowledge/` customiza comportamento por repositório

---

## Limitações Conhecidas

1. **Não auto-dispara:** precisa de `repository_dispatch` do repositório-alvo
2. **Sem comunicação direta entre agentes:** crews isolados, sem mensagens inter-agente em runtime
3. **Crew cooperativo experimental:** `CooperativeAnalysisCrewRunner` ativo apenas via flag
4. **FastAPI inativo:** servidor HTTP disponível mas não usado
5. **Sem painel de métricas:** observabilidade existe no JSON mas sem dashboard
6. **Memória não compartilhada:** cada execução reconstrói contexto; sem estado cross-run além do LanceDB
7. **Um repositório por vez:** sem coordenação multi-repo
8. **Sem agendamento autônomo:** schedule controlado pelo repositório-alvo, não pelo QAgent
