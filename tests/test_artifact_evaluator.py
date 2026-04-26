from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.schemas.review_result import Finding, ReviewResult
from src.schemas.test_strategy_result import (
    TestCase as StrategyTestCase,
    TestStrategyResult as StrategyResult,
)
from src.services.artifact_evaluator import evaluate_artifact


def _artifact_with_review(review_result: ReviewResult) -> FileAnalysisArtifact:
    return FileAnalysisArtifact(
        file_path="src/service.py",
        raw_review_markdown=review_result.summary,
        review_result=review_result,
    )


def test_evaluate_artifact_marks_error_findings_as_high_risk() -> None:
    artifact = _artifact_with_review(
        ReviewResult(
            summary="Mudanca critica em fluxo de autenticacao.",
            findings=[
                Finding(
                    description="Falha critica ao validar credenciais",
                    severity="ERROR",
                )
            ],
            test_needs=["Cobrir login invalido"],
        )
    )
    artifact.test_strategy_result = StrategyResult(
        recommended_tests=[
            StrategyTestCase(
                name="Cobrir login invalido", test_type="UNIT", priority="HIGH"
            )
        ]
    )

    evaluate_artifact(artifact)

    assert artifact.risk_level == "HIGH"
    assert artifact.review_quality == "OK"
    assert artifact.test_generation_recommendation == "RECOMMENDED"


def test_evaluate_artifact_skips_test_generation_without_recommended_tests() -> None:
    artifact = _artifact_with_review(
        ReviewResult(
            summary="Resumo suficientemente descritivo para a avaliacao.",
            findings=[],
            test_needs=[],
        )
    )
    artifact.test_strategy_result = StrategyResult()

    evaluate_artifact(artifact)

    assert artifact.risk_level == "LOW"
    assert artifact.review_quality == "OK"
    assert artifact.test_generation_recommendation == "SKIPPED"


def test_evaluate_artifact_marks_short_summary_as_incomplete() -> None:
    artifact = _artifact_with_review(
        ReviewResult(
            summary="Curto",
            findings=[Finding(description="Cenario incompleto", severity="WARN")],
            test_needs=["Cobrir comportamento parcial"],
        )
    )

    evaluate_artifact(artifact)

    assert artifact.risk_level == "MEDIUM"
    assert artifact.review_quality == "INCOMPLETE"
