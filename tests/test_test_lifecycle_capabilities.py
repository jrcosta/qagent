from pathlib import Path

from src.config.settings import Settings
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.schemas.generated_test_review_result import GeneratedTestsReviewResult
from src.schemas.review_result import ReviewResult
from src.schemas.test_execution_result import TestExecutionResult as ExecutionResult
from src.schemas.test_strategy_result import (
    TestCase as StrategyTestCase,
    TestStrategyResult as StrategyResult,
)
from src.schemas.token_budget import TokenBudgetPlan
from src.services.test_lifecycle_capabilities import (
    TestLifecycleCapabilityExecutor as LifecycleExecutor,
)


class FakeGenerator:
    last_context_result = None
    last_memory_query = "query"
    last_memories_raw = "raw"
    last_memories_used = [{"lesson": "lesson"}]

    def run(self, **kwargs) -> str:
        return (
            "### FILE: tests/test_service.py\n"
            "```python\n"
            "def test_service():\n"
            "    assert True\n"
            "```"
        )


class FakeExecutionRunner:
    def __init__(self, success: bool = True) -> None:
        self.success = success

    def run(self) -> ExecutionResult:
        return ExecutionResult(
            success=self.success,
            exit_code=0 if self.success else 1,
            stdout="ok" if self.success else "failed",
            stderr="",
            duration_seconds=0.1,
            command="pytest",
        )


class FakeReviewer:
    def run(self, **kwargs) -> GeneratedTestsReviewResult:
        return GeneratedTestsReviewResult(
            status="APPROVED",
            summary="Testes válidos.",
            execution_recommended=True,
        )


class FakeFixer:
    def run(self, **kwargs) -> str:
        return (
            "### FILE: tests/test_service.py\n"
            "```python\n"
            "def test_service_fixed():\n"
            "    assert 1 == 1\n"
            "```"
        )


def _artifact() -> FileAnalysisArtifact:
    return FileAnalysisArtifact(
        file_path="src/service.py",
        raw_review_markdown="# Resumo\nMudança.",
        review_result=ReviewResult(
            summary="Mudança com necessidade de testes.",
            test_needs=["Cobrir serviço"],
        ),
        test_strategy_result=StrategyResult(
            recommended_tests=[
                StrategyTestCase(
                    name="Cobrir serviço",
                    test_type="UNIT",
                    priority="MEDIUM",
                )
            ]
        ),
        token_budget_plan=TokenBudgetPlan(
            file_path="src/service.py",
            change_size="small",
            risk_hint="medium",
            analysis_mode="standard",
            context_level="compact",
            include_full_file=True,
            include_memory=True,
            max_context_chars=4000,
            reason="Teste",
        ),
        risk_level="MEDIUM",
        test_generation_recommendation="RECOMMENDED",
    )


def _executor(tmp_path: Path) -> LifecycleExecutor:
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("def service():\n    return True\n", encoding="utf-8")
    executor = LifecycleExecutor(
        settings=Settings(llm_api_key="test"),
        repo_path=tmp_path,
        generator=FakeGenerator(),  # type: ignore[arg-type]
        reviewer=FakeReviewer(),  # type: ignore[arg-type]
        fixer=FakeFixer(),  # type: ignore[arg-type]
        execution_runner=FakeExecutionRunner(),  # type: ignore[arg-type]
    )
    executor._get_diff = lambda artifact: "+ return True"  # type: ignore[method-assign]
    return executor


def test_capabilities_generate_write_execute_and_review(tmp_path: Path) -> None:
    artifact = _artifact()
    executor = _executor(tmp_path)

    for capability in (
        "generate_tests",
        "write_tests",
        "execute_tests",
        "review_tests",
    ):
        executor.run_capability(capability, artifact)

    assert (tmp_path / "tests" / "test_service.py").exists()
    assert artifact.test_execution_result is not None
    assert artifact.test_execution_result.success is True
    assert artifact.generated_test_review_result is not None
    assert artifact.generated_test_review_result.status == "APPROVED"
    assert artifact.memories_used == [{"lesson": "lesson"}]


def test_fix_capability_replaces_and_persists_tests(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact.generated_tests_raw = "old tests"
    artifact.generated_test_files = {
        "tests/test_service.py": "def test_old(): assert False"
    }
    artifact.generated_test_review_result = GeneratedTestsReviewResult(
        status="INVALID",
        summary="Expectativa incorreta.",
        execution_recommended=False,
    )
    artifact.test_execution_result = FakeExecutionRunner(success=False).run()
    executor = _executor(tmp_path)

    executor.run_capability("fix_tests", artifact)

    saved = (tmp_path / "tests" / "test_service.py").read_text(encoding="utf-8")
    assert "test_service_fixed" in saved
    assert "test_auto_fix" in artifact.executed_steps
