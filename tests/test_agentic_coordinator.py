from pathlib import Path

from src.config.settings import Settings
from src.schemas.coordinator_state import CoordinatorState
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.schemas.review_result import ReviewResult
from src.schemas.test_strategy_result import TestCase as StrategyTestCase
from src.schemas.test_strategy_result import TestStrategyResult as StrategyResult
from src.services.agentic_coordinator import AgenticRepositoryCoordinator
from src.services.analysis_pipeline import AnalysisPipelineResult
from src.services.artifact_exporter import export_artifacts_to_json
from src.services.coordinator_state_store import JsonCoordinatorStateStore
from src.services.test_lifecycle_pipeline import (
    TestLifecyclePipelineResult as LifecyclePipelineResult,
)


def _artifact() -> FileAnalysisArtifact:
    return FileAnalysisArtifact(
        file_path="src/service.py",
        review_result=ReviewResult(
            summary="Mudança analisada com contratos completos.",
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


class FakeAnalysisPipeline:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, **kwargs) -> AnalysisPipelineResult:
        self.calls += 1
        report = Path(kwargs["output_file"])
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("# análise", encoding="utf-8")
        artifacts = [_artifact()]
        artifacts_file = export_artifacts_to_json(
            artifacts,
            str(report.parent),
        )
        summary = report.parent / "run_summary.json"
        summary.write_text("{}", encoding="utf-8")
        return AnalysisPipelineResult(
            artifacts=artifacts,
            report_file=report,
            artifacts_file=artifacts_file,
            summary_file=summary,
        )


class FakeLifecyclePipeline:
    def __init__(self, escalated: int = 0) -> None:
        self.calls = 0
        self.escalated = escalated

    def run(self, **kwargs) -> LifecyclePipelineResult:
        self.calls += 1
        artifacts = kwargs["artifacts"]
        for artifact in artifacts:
            artifact.agentic_run_status = (
                "ESCALATED" if self.escalated else "COMPLETED"
            )
        export_artifacts_to_json(artifacts, str(kwargs["output_dir"]))
        return LifecyclePipelineResult(
            artifacts=artifacts,
            eligible_files=len(artifacts),
            escalated_files=self.escalated,
        )


def test_coordinator_runs_analysis_and_test_lifecycle(tmp_path: Path) -> None:
    analysis = FakeAnalysisPipeline()
    lifecycle = FakeLifecyclePipeline()
    store = JsonCoordinatorStateStore(tmp_path / "states")
    coordinator = AgenticRepositoryCoordinator(
        Settings(),
        state_store=store,
        analysis_pipeline=analysis,  # type: ignore[arg-type]
        lifecycle_pipeline=lifecycle,  # type: ignore[arg-type]
    )

    state = coordinator.run(
        repo_path=tmp_path,
        output_dir=tmp_path / "outputs",
        base_sha="base",
        head_sha="head",
    )

    assert state.status == "COMPLETED"
    assert state.eligible_files == 1
    assert state.escalated_files == 0
    assert analysis.calls == 1
    assert lifecycle.calls == 1
    assert store.load(state.run_id).status == "COMPLETED"


def test_coordinator_propagates_lifecycle_escalation(tmp_path: Path) -> None:
    coordinator = AgenticRepositoryCoordinator(
        Settings(),
        state_store=JsonCoordinatorStateStore(tmp_path / "states"),
        analysis_pipeline=FakeAnalysisPipeline(),  # type: ignore[arg-type]
        lifecycle_pipeline=FakeLifecyclePipeline(escalated=1),  # type: ignore[arg-type]
    )

    state = coordinator.run(
        repo_path=tmp_path,
        output_dir=tmp_path / "outputs",
    )

    assert state.status == "ESCALATED"
    assert state.escalated_files == 1


def test_resume_after_analysis_skips_completed_stage(tmp_path: Path) -> None:
    output = tmp_path / "outputs"
    artifacts_file = export_artifacts_to_json([_artifact()], str(output))
    analysis = FakeAnalysisPipeline()
    lifecycle = FakeLifecyclePipeline()
    store = JsonCoordinatorStateStore(tmp_path / "states")
    state = CoordinatorState(
        repo_path=str(tmp_path),
        output_dir=str(output),
        status="ANALYSIS_COMPLETED",
        artifacts_file=str(artifacts_file),
        analysis_report_file=str(output / "analysis.md"),
    )
    store.save(state)
    coordinator = AgenticRepositoryCoordinator(
        Settings(),
        state_store=store,
        analysis_pipeline=analysis,  # type: ignore[arg-type]
        lifecycle_pipeline=lifecycle,  # type: ignore[arg-type]
    )

    resumed = coordinator.resume(state.run_id)

    assert resumed.status == "COMPLETED"
    assert analysis.calls == 0
    assert lifecycle.calls == 1
