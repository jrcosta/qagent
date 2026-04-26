from src.crew.high_risk_strategy_crew import HighRiskTestStrategyRunner
from src.schemas.review_result import ReviewResult
from src.schemas.test_strategy_result import (
    TestCase as StrategyTestCase,
    TestStrategyResult as StrategyResult,
)


def test_high_risk_runner_returns_base_strategy_when_llm_fails(monkeypatch) -> None:
    runner = HighRiskTestStrategyRunner(settings=None)  # type: ignore[arg-type]
    base_strategy = StrategyResult(
        recommended_tests=[
            StrategyTestCase(name="Cobrir regressao critica", priority="HIGH")
        ],
        notes="base",
    )

    def raise_error(**kwargs):
        raise RuntimeError("LLM indisponivel")

    monkeypatch.setattr(runner, "_run_crew", raise_error)

    result = runner.run(
        file_path="src/auth.py",
        review_result=ReviewResult(
            summary="Mudanca critica.",
            findings=[],
            test_needs=[],
        ),
        base_strategy=base_strategy,
    )

    assert result is base_strategy
