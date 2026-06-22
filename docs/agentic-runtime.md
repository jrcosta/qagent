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
retomada sem repetir passos concluídos.

### Evaluator determinístico

Após cada passo, o evaluator decide:

- `CONTINUE`: executar o próximo passo;
- `RETRY`: repetir uma falha dentro do limite;
- `CORRECT`: inserir capacidades corretivas autorizadas;
- `COMPLETE`: concluir;
- `ESCALATE`: interromper e solicitar validação humana.

Há no máximo um ciclo de correção automática. Reviews incompletos, tentativas
esgotadas e estados finais inconsistentes são escalados. Uma escalação define
`test_generation_recommendation=SKIPPED`, impedindo automação downstream até
validação humana.

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

- O runtime cobre inicialmente o pipeline pós-review de cada arquivo.
- O catálogo ainda não inclui geração, execução e revisão de testes.
- A persistência é local em JSON; execução distribuída exigirá um state store
  transacional.
- O planner escolhe passos, mas políticas de segurança, retries e escalação
  permanecem determinísticas.
