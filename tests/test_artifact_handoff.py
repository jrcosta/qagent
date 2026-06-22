import json
from pathlib import Path

from src.main_test_generator import (
    load_generation_artifacts,
    render_report_from_artifacts,
)
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.schemas.review_result import Finding, ReviewResult
from src.schemas.test_strategy_result import TestCase as StrategyTestCase
from src.schemas.test_strategy_result import TestStrategyResult as StrategyResult
from src.schemas.token_budget import TokenBudgetPlan
from src.services.artifact_exporter import (
    export_artifacts_to_json,
    load_artifacts_from_json,
)


class FailingOrchestrator:
    def run_artifact_pipeline(self, artifact):
        raise AssertionError("O handoff estruturado não deve reexecutar o orquestrador")


class FailingPlanner:
    def plan(self, **kwargs):
        raise AssertionError("O handoff estruturado não deve recalcular o orçamento")


def _artifact() -> FileAnalysisArtifact:
    return FileAnalysisArtifact(
        file_path="src/payment_service.py",
        token_budget_plan=TokenBudgetPlan(
            file_path="src/payment_service.py",
            change_size="medium",
            risk_hint="high",
            analysis_mode="cooperative",
            context_level="standard",
            include_full_file=True,
            include_memory=True,
            max_context_chars=8000,
            reason="Plano produzido na análise.",
        ),
        raw_review_markdown="# Tipo da mudança\nAlteração de pagamento.",
        review_result=ReviewResult(
            summary="Mudança crítica no processamento de pagamentos.",
            findings=[
                Finding(
                    description="Cobrança pode ser processada duas vezes",
                    severity="ERROR",
                )
            ],
            test_needs=["Cobrir idempotência da cobrança"],
        ),
        test_strategy_result=StrategyResult(
            recommended_tests=[
                StrategyTestCase(
                    name="impedir cobrança duplicada",
                    test_type="INTEGRATION",
                    priority="HIGH",
                )
            ],
            notes="Estratégia validada na etapa de análise.",
        ),
        risk_level="HIGH",
        review_quality="OK",
        test_generation_recommendation="RECOMMENDED",
        executed_steps=["qa_review", "evaluate_risk", "build_strategy"],
        applied_policies=["cooperative_analysis_experimental", "strategy_HIGH"],
    )


def test_artifact_round_trip_preserves_analysis_decisions(tmp_path: Path) -> None:
    source = _artifact()
    path = export_artifacts_to_json([source], str(tmp_path))

    loaded = load_artifacts_from_json(path)

    assert len(loaded) == 1
    artifact = loaded[0]
    assert artifact.risk_level == "HIGH"
    assert artifact.test_strategy_result == source.test_strategy_result
    assert artifact.token_budget_plan == source.token_budget_plan
    assert artifact.executed_steps == source.executed_steps
    assert artifact.applied_policies == source.applied_policies


def test_generation_prefers_structured_handoff_without_reprocessing(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    report_path = tmp_path / "outputs" / "analysis.md"
    artifacts_path = tmp_path / "outputs" / "artifacts.json"
    artifacts_path.parent.mkdir()
    artifacts_path.write_text(
        json.dumps([_artifact().model_dump(mode="json")]),
        encoding="utf-8",
    )

    artifacts, selected_path, used_legacy = load_generation_artifacts(
        artifacts_file=str(artifacts_path),
        report_file=str(report_path),
        repo_path=repo_path,
        base_sha=None,
        head_sha=None,
        orchestrator=FailingOrchestrator(),  # type: ignore[arg-type]
        token_budget_planner=FailingPlanner(),  # type: ignore[arg-type]
    )

    assert selected_path == artifacts_path
    assert used_legacy is False
    assert artifacts[0].risk_level == "HIGH"
    assert artifacts[0].test_strategy_result is not None
    assert artifacts[0].test_strategy_result.notes == (
        "Estratégia validada na etapa de análise."
    )


def test_render_report_uses_raw_markdown_without_parsing() -> None:
    report = render_report_from_artifacts([_artifact()])

    assert "# Arquivo analisado: src/payment_service.py" in report
    assert "# Tipo da mudança\nAlteração de pagamento." in report
