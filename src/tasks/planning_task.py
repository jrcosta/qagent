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
        phase: str = "analysis",
    ) -> Task:
        if phase == "test_lifecycle":
            phase_rules = """
- use phase='test_lifecycle'
- sempre comece por generate_tests
- write_tests depende de generate_tests
- execute_tests depende de write_tests
- review_tests depende de execute_tests e deve ser o último passo
- não inclua fix_tests no plano inicial; o evaluator decide correções
"""
        else:
            phase_rules = """
- use phase='analysis'
- sempre comece por evaluate_risk
- build_test_strategy depende de evaluate_risk
- enrich_high_risk só deve aparecer quando houver finding ERROR ou risco alto
- evaluate_final deve ser o último passo
"""
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
{phase_rules}
- use IDs curtos e únicos
- não crie mais passos que o necessário
""",
            expected_output="ExecutionPlan válido usando apenas o catálogo autorizado.",
            agent=agent,
            output_pydantic=ExecutionPlan,
        )
