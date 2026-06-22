from crewai import Task

from src.schemas.agentic_runtime import ExecutionPlan


class PlanningTaskFactory:
    @staticmethod
    def create(
        agent,
        *,
        file_path: str,
        risk_hint: str,
        review_summary: str,
        findings_summary: str,
        capability_catalog: str,
    ) -> Task:
        return Task(
            description=f"""
Planeje a execução pós-review para o arquivo `{file_path}`.

Sinal inicial de risco: {risk_hint}
Resumo do review: {review_summary}
Findings:
{findings_summary or "- nenhum"}

Catálogo autorizado:
{capability_catalog}

Regras obrigatórias:
- use somente capabilities presentes no catálogo
- sempre comece por evaluate_risk
- build_test_strategy depende de evaluate_risk
- enrich_high_risk só deve aparecer quando houver finding ERROR ou risco alto
- evaluate_final deve ser o último passo
- use IDs curtos e únicos
- não crie mais passos que o necessário
""",
            expected_output="ExecutionPlan válido usando apenas o catálogo autorizado.",
            agent=agent,
            output_pydantic=ExecutionPlan,
        )

