from pathlib import Path

from src.config.settings import Settings
from src.schemas.coordinator_state import CoordinatorState
from src.services.analysis_pipeline import RepositoryAnalysisPipeline
from src.services.artifact_exporter import load_artifacts_from_json
from src.services.coordinator_state_store import JsonCoordinatorStateStore
from src.services.test_lifecycle_pipeline import RepositoryTestLifecyclePipeline


class AgenticRepositoryCoordinator:
    """Coordena análise e ciclo de testes em uma única execução persistente."""

    def __init__(
        self,
        settings: Settings,
        *,
        state_store: JsonCoordinatorStateStore,
        analysis_pipeline: RepositoryAnalysisPipeline | None = None,
        lifecycle_pipeline: RepositoryTestLifecyclePipeline | None = None,
    ) -> None:
        self.settings = settings
        self.state_store = state_store
        self.analysis_pipeline = analysis_pipeline or RepositoryAnalysisPipeline(
            settings
        )
        self.lifecycle_pipeline = lifecycle_pipeline or (
            RepositoryTestLifecyclePipeline(settings)
        )

    def run(
        self,
        *,
        repo_path: str | Path,
        output_dir: str | Path,
        base_sha: str | None = None,
        head_sha: str | None = None,
        cooperative_analysis: bool = False,
        run_id: str | None = None,
        run_test_lifecycle: bool = True,
    ) -> CoordinatorState:
        output = Path(output_dir).resolve()
        output.mkdir(parents=True, exist_ok=True)
        state = CoordinatorState(
            **({"run_id": run_id} if run_id else {}),
            repo_path=str(Path(repo_path).resolve()),
            output_dir=str(output),
            base_sha=base_sha,
            head_sha=head_sha,
            cooperative_analysis=cooperative_analysis,
            run_test_lifecycle=run_test_lifecycle,
        )
        self.state_store.save(state)
        return self._execute(state)

    def resume(
        self,
        run_id: str,
        repo_path: str | Path | None = None,
    ) -> CoordinatorState:
        state = self.state_store.load(run_id)
        if repo_path is not None:
            state.repo_path = str(Path(repo_path).resolve())
        if state.status in {"COMPLETED", "ESCALATED"}:
            return state
        if state.status == "FAILED":
            state.status = (
                "ANALYSIS_COMPLETED"
                if state.artifacts_file
                else "PENDING"
            )
            state.error = None
            self.state_store.save(state)
        return self._execute(state)

    def _execute(self, state: CoordinatorState) -> CoordinatorState:
        try:
            if state.status in {"PENDING", "ANALYSIS_RUNNING"}:
                state.status = "ANALYSIS_RUNNING"
                self.state_store.save(state)
                analysis = self.analysis_pipeline.run(
                    repo_path=state.repo_path,
                    output_file=Path(state.output_dir) / "analysis.md",
                    base_sha=state.base_sha,
                    head_sha=state.head_sha,
                    cooperative_analysis=state.cooperative_analysis,
                    agentic_runtime=True,
                    run_state_dir=(
                        Path(state.output_dir) / "run_states" / "analysis"
                    ),
                )
                state.artifacts_file = str(analysis.artifacts_file)
                state.analysis_report_file = str(analysis.report_file)
                state.status = "ANALYSIS_COMPLETED"
                self.state_store.save(state)

                if not state.run_test_lifecycle:
                    state.status = "COMPLETED"
                    self.state_store.save(state)
                    return state

            if state.status in {
                "ANALYSIS_COMPLETED",
                "TEST_LIFECYCLE_RUNNING",
            }:
                if not state.artifacts_file:
                    raise ValueError("artifacts_file ausente após análise")
                state.status = "TEST_LIFECYCLE_RUNNING"
                self.state_store.save(state)
                artifacts = load_artifacts_from_json(state.artifacts_file)
                lifecycle = self.lifecycle_pipeline.run(
                    artifacts=artifacts,
                    repo_path=state.repo_path,
                    output_dir=state.output_dir,
                    base_sha=state.base_sha,
                    head_sha=state.head_sha,
                    run_state_dir=(
                        Path(state.output_dir)
                        / "run_states"
                        / "test_lifecycle"
                    ),
                )
                state.eligible_files = lifecycle.eligible_files
                state.escalated_files = lifecycle.escalated_files
                state.status = (
                    "ESCALATED"
                    if lifecycle.escalated_files
                    else "COMPLETED"
                )
                self.state_store.save(state)
            return state
        except Exception as exc:
            state.status = "FAILED"
            state.error = str(exc)
            self.state_store.save(state)
            raise
