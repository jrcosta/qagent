from crewai import Crew, Process

from src.agent.planner_agent import PlannerAgentFactory
from src.config.settings import Settings
from src.schemas.agentic_runtime import ExecutionPlan, PlanStep
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.services.capability_catalog import (
    render_capability_catalog,
    validate_execution_plan,
)
from src.tasks.planning_task import PlanningTaskFactory


class PlannerCrewRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def plan(self, artifact: FileAnalysisArtifact) -> ExecutionPlan:
        if (
            not self.settings.llm_api_key
            or (
                artifact.token_budget_plan is not None
                and artifact.token_budget_plan.analysis_mode == "skip"
            )
        ):
            return build_deterministic_plan(artifact)

        try:
            agent = PlannerAgentFactory(self.settings).create()
            findings = "\n".join(
                f"- [{finding.severity}] {finding.description}"
                for finding in (
                    artifact.review_result.findings
                    if artifact.review_result
                    else []
                )
            )
            task = PlanningTaskFactory.create(
                agent,
                file_path=artifact.file_path,
                risk_hint=(
                    artifact.token_budget_plan.risk_hint
                    if artifact.token_budget_plan
                    else "unknown"
                ),
                review_summary=(
                    artifact.review_result.summary
                    if artifact.review_result
                    else "review ausente"
                ),
                findings_summary=findings,
                capability_catalog=render_capability_catalog(),
            )
            result = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=True,
            ).kickoff()
            plan = _extract_plan(result)
            validate_execution_plan(plan)
            plan.planner_source = "llm"
            return plan
        except Exception as exc:
            plan = build_deterministic_plan(artifact)
            plan.rationale += f" Fallback do planner: {exc}"
            return plan

    def plan_test_lifecycle(
        self,
        artifact: FileAnalysisArtifact,
    ) -> ExecutionPlan:
        if not self.settings.llm_api_key:
            return build_test_lifecycle_plan(artifact)

        try:
            agent = PlannerAgentFactory(self.settings).create()
            findings = "\n".join(
                f"- [{finding.severity}] {finding.description}"
                for finding in (
                    artifact.review_result.findings
                    if artifact.review_result
                    else []
                )
            )
            task = PlanningTaskFactory.create(
                agent,
                file_path=artifact.file_path,
                risk_hint=artifact.risk_level,
                review_summary=(
                    artifact.review_result.summary
                    if artifact.review_result
                    else "review ausente"
                ),
                findings_summary=findings,
                capability_catalog=render_capability_catalog(),
                phase="test_lifecycle",
            )
            result = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=True,
            ).kickoff()
            plan = _extract_plan(result)
            plan.phase = "test_lifecycle"
            validate_execution_plan(plan)
            plan.planner_source = "llm"
            return plan
        except Exception as exc:
            plan = build_test_lifecycle_plan(artifact)
            plan.rationale += f" Fallback do planner: {exc}"
            return plan


def _extract_plan(result) -> ExecutionPlan:
    candidates = []
    if getattr(result, "tasks_output", None):
        candidates.append(result.tasks_output[-1])
    candidates.append(result)

    for candidate in candidates:
        pydantic_output = getattr(candidate, "pydantic", None)
        if pydantic_output is not None:
            return ExecutionPlan.model_validate(pydantic_output)
        json_output = getattr(candidate, "json_dict", None)
        if json_output:
            return ExecutionPlan.model_validate(json_output)
    raise ValueError("Planner não retornou ExecutionPlan estruturado")


def validate_plan_capabilities(plan: ExecutionPlan) -> None:
    """Alias de compatibilidade para consumidores do runner."""
    validate_execution_plan(plan)


def build_deterministic_plan(artifact: FileAnalysisArtifact) -> ExecutionPlan:
    has_error = bool(
        artifact.review_result
        and any(finding.severity == "ERROR" for finding in artifact.review_result.findings)
    )
    steps = [
        PlanStep(
            id="risk",
            capability="evaluate_risk",
            reason="Classificar risco por política determinística.",
        ),
        PlanStep(
            id="strategy",
            capability="build_test_strategy",
            reason="Construir estratégia tipada após classificação.",
            depends_on=["risk"],
        ),
    ]
    if has_error:
        steps.append(
            PlanStep(
                id="high-risk",
                capability="enrich_high_risk",
                reason="Finding ERROR exige refinamento especializado.",
                depends_on=["strategy"],
                max_attempts=2,
            )
        )
    steps.append(
        PlanStep(
            id="final",
            capability="evaluate_final",
            reason="Consolidar recomendação final.",
            depends_on=[steps[-1].id],
        )
    )
    return ExecutionPlan(
        objective=f"Concluir análise governada de {artifact.file_path}",
        steps=steps,
        rationale="Plano seguro derivado de regras determinísticas.",
        planner_source="deterministic_fallback",
    )


def build_test_lifecycle_plan(
    artifact: FileAnalysisArtifact,
) -> ExecutionPlan:
    return ExecutionPlan(
        objective=f"Gerar e validar testes para {artifact.file_path}",
        phase="test_lifecycle",
        planner_source="deterministic_fallback",
        rationale=(
            "Ciclo seguro: gerar, persistir localmente, executar e revisar. "
            "Correções dependem do evaluator."
        ),
        steps=[
            PlanStep(
                id="generate",
                capability="generate_tests",
                reason="Transformar estratégia aprovada em testes executáveis.",
                max_attempts=2,
            ),
            PlanStep(
                id="write",
                capability="write_tests",
                reason="Persistir testes antes da execução real.",
                depends_on=["generate"],
            ),
            PlanStep(
                id="execute",
                capability="execute_tests",
                reason="Obter evidência real da suíte.",
                depends_on=["write"],
                max_attempts=2,
            ),
            PlanStep(
                id="review",
                capability="review_tests",
                reason="Validar coerência, cobertura e resultado da execução.",
                depends_on=["execute"],
                max_attempts=2,
            ),
        ],
    )
