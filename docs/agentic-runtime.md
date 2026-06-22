# Runtime agêntico governado

## Objetivo

O runtime agêntico adiciona planejamento dinâmico e replanejamento controlado
sem entregar decisões críticas diretamente ao LLM.

Ele é opt-in e não substitui o pipeline determinístico padrão:

```bash
python -m src.main \
  --repo-path ./meu-repo \
  --base-sha COMMIT_A \
  --head-sha COMMIT_B \
  --output-file outputs/analysis.md \
  --agentic-runtime
```

Os estados são persistidos por padrão em `outputs/run_states/`. Outro diretório
pode ser informado com `--run-state-dir`.

Após a análise, o ciclo local completo de testes pode ser executado com:

```bash
python -m src.main_agentic_lifecycle \
  --repo-path ./meu-repo \
  --artifacts-file outputs/artifacts.json \
  --base-sha COMMIT_A \
  --head-sha COMMIT_B \
  --fail-on-escalation
```

Esse entrypoint pode gerar e escrever arquivos no repositório local, executar a
suíte, revisar e corrigir os testes. Ele não faz commit, push, abre PR ou publica
comentários.

## Coordinator persistente

O fluxo completo pode ser iniciado por um único entrypoint:

```bash
python -m src.main_agentic \
  --repo-path ./meu-repo \
  --output-dir outputs \
  --base-sha COMMIT_A \
  --head-sha COMMIT_B \
  --fail-on-escalation
```

O `AgenticRepositoryCoordinator` persiste um estado de nível superior:

```text
PENDING
  → ANALYSIS_RUNNING
  → ANALYSIS_COMPLETED
  → TEST_LIFECYCLE_RUNNING
  → COMPLETED | ESCALATED | FAILED
```

Para retomar:

```bash
python -m src.main_agentic \
  --output-dir outputs \
  --resume-run-id <coordinator-run-id>
```

Quando a análise já foi concluída, o coordinator carrega `artifacts.json` e
segue diretamente para testes. Dentro do ciclo, arquivos `COMPLETED` ou
`ESCALATED` são preservados e não executam novamente.

## Componentes

### `ExecutionPlan`

Contrato Pydantic produzido pelo Planner Agent. Cada passo contém:

- capability autorizada;
- dependências explícitas;
- justificativa;
- limite de tentativas.

O plano deve começar com `evaluate_risk`, conter exatamente uma construção de
estratégia e terminar com `evaluate_final`.

### Catálogo de capacidades

O planner não pode criar ferramentas ou comandos arbitrários. O catálogo atual é:

| Capability | Responsabilidade |
|---|---|
| `evaluate_risk` | Classificação determinística de risco e qualidade |
| `build_test_strategy` | Construção da estratégia tipada |
| `enrich_high_risk` | Refinamento LLM exclusivo para risco HIGH |
| `evaluate_final` | Consolidação da recomendação final |
| `generate_tests` | Geração de testes a partir do artefato |
| `write_tests` | Escrita local dos testes |
| `execute_tests` | Execução real da suíte |
| `review_tests` | Revisão crítica com evidência da execução |
| `fix_tests` | Correção e persistência local após reprovação |

Planos fora desse catálogo ou sem pré-requisitos são rejeitados. Quando o
planner LLM falha, o runtime usa um plano determinístico seguro.

### `RunState`

Estado persistido após cada transição:

- plano em execução;
- status e tentativas de cada passo;
- decisões do evaluator;
- snapshot do `FileAnalysisArtifact`;
- estado terminal da execução.

A escrita usa arquivo temporário e substituição atômica. O runtime oferece
retomada sem repetir passos concluídos. Ao iniciar um novo stage, a execução
anterior é preservada em `agentic_run_history`.

### Evaluator determinístico

Após cada passo, o evaluator decide:

- `CONTINUE`: executar o próximo passo;
- `RETRY`: repetir uma falha dentro do limite;
- `CORRECT`: inserir capacidades corretivas autorizadas;
- `COMPLETE`: concluir;
- `ESCALATE`: interromper e solicitar validação humana.

Há no máximo um ciclo de correção automática. Reviews incompletos, tentativas
esgotadas e estados finais inconsistentes são escalados. Na fase de análise,
uma escalação define `test_generation_recommendation=SKIPPED`. No ciclo de
testes, use `--fail-on-escalation` para bloquear automação downstream até
validação humana.

No ciclo de testes, falha de execução ou revisão `NEEDS_CHANGES`/`INVALID`
autoriza a sequência corretiva:

```text
fix_tests → execute_tests → review_tests
```

Uma segunda reprovação é escalada.

## Fluxo

```text
ReviewResult
    ↓
Planner Agent
    ↓
Validação do catálogo e DAG
    ↓
GovernedAgenticRuntime
    ├─ executa capability
    ├─ persiste RunState + artefato
    └─ solicita decisão ao Evaluator
          ├─ continue
          ├─ retry
          ├─ correct
          ├─ complete
          └─ escalate
```

## Limites atuais

- O runtime cobre análise pós-review e ciclo local completo de testes.
- A persistência é local em JSON; execução distribuída exigirá um state store
  transacional.
- O planner escolhe passos, mas políticas de segurança, retries e escalação
  permanecem determinísticas.
- Efeitos externos de GitHub continuam fora do catálogo governado.
- A retomada automática é baseada nos checkpoints JSON locais; execução
  distribuída ainda exige um store transacional.
