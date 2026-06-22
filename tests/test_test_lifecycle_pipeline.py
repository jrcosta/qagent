from pathlib import Path

from src.config.settings import Settings
from src.crew.planning_crew import build_test_lifecycle_plan
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.schemas.review_result import ReviewResult
from src.schemas.test_strategy_result import (
    TestCase as StrategyTestCase,
    TestStrategyResult as StrategyResult,
)
from src.services.test_lifecycle_pipeline import RepositoryTestLifecyclePipeline


class FailingPlanner:
    def plan_test_lifecycle(self, artifact):
        raise AssertionError("stage concluído não deve ser planejado novamente")


class UnusedExecutor:
    def run_capability(self, capability, artifact):
        raise AssertionError("stage concluído não deve ser executado novamente")


def test_pipeline_skips_completed_lifecycle_on_resume(tmp_path: Path) -> None:
    artifact = FileAnalysisArtifact(
        file_path="src/service.py",
        review_result=ReviewResult(
            summary="Análise completa para retomada.",
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
        test_generation_recommendation="RECOMMENDED",
    )
    artifact.execution_plan = build_test_lifecycle_plan(artifact)
    artifact.agentic_run_id = "completed-run"
    artifact.agentic_run_status = "COMPLETED"

    result = RepositoryTestLifecyclePipeline(
        Settings(),
        planner=FailingPlanner(),  # type: ignore[arg-type]
        executor=UnusedExecutor(),  # type: ignore[arg-type]
    ).run(
        artifacts=[artifact],
        repo_path=tmp_path,
        output_dir=tmp_path / "outputs",
    )

    assert result.eligible_files == 1
    assert result.escalated_files == 0
    assert artifact.agentic_run_status == "COMPLETED"
