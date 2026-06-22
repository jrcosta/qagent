from src.schemas.agentic_runtime import EvaluationDecision, RunState
from src.schemas.file_analysis_artifact import FileAnalysisArtifact


class AgenticRunEvaluator:
    """Decide transições sem delegar controle crítico ao LLM."""

    def evaluate_step(
        self,
        state: RunState,
        artifact: FileAnalysisArtifact,
        *,
        step_failed: bool,
    ) -> EvaluationDecision:
        current = _current_record(state)
        planned_step = next(
            step for step in state.plan.steps if step.id == current.step_id
        )

        if step_failed:
            if current.attempts < planned_step.max_attempts:
                return EvaluationDecision(
                    action="RETRY",
                    target_step_id=current.step_id,
                    reason="Falha recuperável e orçamento de tentativas disponível.",
                )
            return EvaluationDecision(
                action="ESCALATE",
                target_step_id=current.step_id,
                reason="Capacidade falhou após esgotar as tentativas permitidas.",
            )

        if any(record.status == "PENDING" for record in state.steps):
            return EvaluationDecision(
                action="CONTINUE",
                reason="Há passos planejados ainda não executados.",
            )

        return self.evaluate_completion(state, artifact)

    def evaluate_completion(
        self,
        state: RunState,
        artifact: FileAnalysisArtifact,
    ) -> EvaluationDecision:
        if artifact.review_quality == "INCOMPLETE":
            return EvaluationDecision(
                action="ESCALATE",
                reason="Review incompleto exige validação humana.",
            )

        if (
            artifact.risk_level == "HIGH"
            and "high_risk_enrichment" not in artifact.executed_steps
            and state.correction_cycles == 0
        ):
            return EvaluationDecision(
                action="CORRECT",
                reason="Risco HIGH sem enriquecimento especializado.",
                correction_capabilities=["enrich_high_risk", "evaluate_final"],
            )

        if (
            artifact.test_generation_recommendation == "RECOMMENDED"
            and artifact.test_strategy_result
            and artifact.test_strategy_result.recommended_tests
        ):
            return EvaluationDecision(
                action="COMPLETE",
                reason="Estratégia válida e geração de testes recomendada.",
            )

        if (
            artifact.test_generation_recommendation == "SKIPPED"
            and artifact.review_result
            and not artifact.review_result.test_needs
        ):
            return EvaluationDecision(
                action="COMPLETE",
                reason="Review válido sem necessidade de novos testes.",
            )

        return EvaluationDecision(
            action="ESCALATE",
            reason="Estado final inconsistente requer decisão humana.",
        )


def _current_record(state: RunState):
    return next(record for record in state.steps if record.step_id == state.current_step_id)

