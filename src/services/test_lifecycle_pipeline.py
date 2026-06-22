from dataclasses import dataclass
from pathlib import Path
import time

from src.config.settings import Settings
from src.crew.planning_crew import PlannerCrewRunner
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.services.agentic_runtime import GovernedAgenticRuntime
from src.services.artifact_exporter import (
    export_artifacts_to_json,
    export_run_summary,
)
from src.services.run_state_store import JsonRunStateStore
from src.services.test_lifecycle_capabilities import (
    TestLifecycleCapabilityExecutor,
)


@dataclass
class TestLifecyclePipelineResult:
    artifacts: list[FileAnalysisArtifact]
    eligible_files: int
    escalated_files: int


class RepositoryTestLifecyclePipeline:
    def __init__(
        self,
        settings: Settings,
        *,
        planner: PlannerCrewRunner | None = None,
        executor: TestLifecycleCapabilityExecutor | None = None,
    ) -> None:
        self.settings = settings
        self.planner = planner or PlannerCrewRunner(settings)
        self.executor = executor

    def run(
        self,
        *,
        artifacts: list[FileAnalysisArtifact],
        repo_path: str | Path,
        output_dir: str | Path,
        base_sha: str | None = None,
        head_sha: str | None = None,
        run_state_dir: str | Path | None = None,
    ) -> TestLifecyclePipelineResult:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        executor = self.executor or TestLifecycleCapabilityExecutor(
            settings=self.settings,
            repo_path=repo_path,
            base_sha=base_sha,
            head_sha=head_sha,
        )
        runtime = GovernedAgenticRuntime(
            orchestrator=executor,  # type: ignore[arg-type]
            state_store=JsonRunStateStore(
                run_state_dir or output / "run_states" / "test_lifecycle"
            ),
        )
        started = time.perf_counter()
        eligible = 0
        escalated = 0

        for artifact in artifacts:
            if artifact.test_generation_recommendation != "RECOMMENDED":
                artifact.mark_step_skipped(
                    "agentic_test_lifecycle",
                    "geração de testes não recomendada",
                )
                continue
            if artifact.review_result is None or artifact.test_strategy_result is None:
                artifact.mark_step_skipped(
                    "agentic_test_lifecycle",
                    "contratos de análise incompletos",
                )
                artifact.add_policy("agentic_human_escalation")
                artifact.add_note(
                    "Escalação agêntica: contratos necessários ao ciclo ausentes."
                )
                artifact.agentic_run_status = "ESCALATED"
                escalated += 1
                continue

            eligible += 1
            is_test_lifecycle = bool(
                artifact.execution_plan
                and artifact.execution_plan.phase == "test_lifecycle"
            )
            if is_test_lifecycle and artifact.agentic_run_status == "COMPLETED":
                continue
            if is_test_lifecycle and artifact.agentic_run_status == "ESCALATED":
                escalated += 1
                continue

            if (
                is_test_lifecycle
                and artifact.agentic_run_status in {"PENDING", "RUNNING"}
                and artifact.agentic_run_id
            ):
                state = runtime.resume(artifact, artifact.agentic_run_id)
            else:
                plan = self.planner.plan_test_lifecycle(artifact)
                artifact.add_policy(
                    f"test_lifecycle_planner_{plan.planner_source}"
                )
                artifact.add_note(f"Planner de testes: {plan.rationale}")
                state = runtime.run(artifact, plan)
            artifact.add_policy("governed_test_lifecycle")
            artifact.add_note(
                f"Ciclo de testes {state.run_id} finalizado como {state.status}."
            )
            if state.status == "ESCALATED":
                escalated += 1
            export_artifacts_to_json(artifacts, str(output))

        export_artifacts_to_json(artifacts, str(output))
        export_run_summary(
            artifacts,
            str(output),
            (time.perf_counter() - started) * 1000,
        )
        return TestLifecyclePipelineResult(
            artifacts=artifacts,
            eligible_files=eligible,
            escalated_files=escalated,
        )
