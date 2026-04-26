from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.schemas.review_result import Finding, ReviewResult
from src.schemas.test_strategy_result import TestStrategyResult as StrategyResult
from src.services.analysis_orchestrator import AnalysisOrchestrator


class FakeHighRiskRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, **kwargs) -> StrategyResult:
        self.calls += 1
        base_strategy = kwargs["base_strategy"]
        base_strategy.notes += "\nrefinado"
        return base_strategy


def test_orchestrator_skips_high_risk_agent_for_low_risk_artifact() -> None:
    runner = FakeHighRiskRunner()
    orchestrator = AnalysisOrchestrator(runner)  # type: ignore[arg-type]
    artifact = FileAnalysisArtifact(
        file_path="src/service.py",
        review_result=ReviewResult(
            summary="Mudanca simples com teste direto.",
            findings=[],
            test_needs=["Cobrir caso feliz"],
        ),
    )

    orchestrator.run_artifact_pipeline(artifact)

    assert runner.calls == 0
    assert artifact.risk_level == "LOW"
    assert "evaluate_risk" in artifact.executed_steps
    assert "build_strategy" in artifact.executed_steps
    assert "evaluate_final" in artifact.executed_steps
    assert artifact.skipped_steps == ["high_risk_enrichment: risk_level=LOW"]
    assert artifact.test_generation_recommendation == "RECOMMENDED"


def test_orchestrator_calls_high_risk_agent_for_error_findings() -> None:
    runner = FakeHighRiskRunner()
    orchestrator = AnalysisOrchestrator(runner)  # type: ignore[arg-type]
    artifact = FileAnalysisArtifact(
        file_path="src/auth.py",
        review_result=ReviewResult(
            summary="Mudanca critica no fluxo de autenticacao.",
            findings=[
                Finding(
                    description="Falha critica ao validar sessao",
                    severity="ERROR",
                )
            ],
            test_needs=["Cobrir sessao invalida"],
        ),
    )

    orchestrator.run_artifact_pipeline(artifact)

    assert runner.calls == 1
    assert artifact.risk_level == "HIGH"
    assert "high_risk_enrichment" in artifact.executed_steps
    assert "high_risk_llm_enrichment" in artifact.applied_policies
    assert artifact.test_strategy_result is not None
    assert "refinado" in artifact.test_strategy_result.notes
