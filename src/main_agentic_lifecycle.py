from argparse import ArgumentParser
from pathlib import Path
import sys
import time

from src.config.settings import get_settings
from src.crew.planning_crew import PlannerCrewRunner
from src.services.agentic_runtime import GovernedAgenticRuntime
from src.services.artifact_exporter import (
    export_artifacts_to_json,
    export_run_summary,
    load_artifacts_from_json,
)
from src.services.run_state_store import JsonRunStateStore
from src.services.test_lifecycle_capabilities import (
    TestLifecycleCapabilityExecutor,
)


def parse_args():
    parser = ArgumentParser(
        description="Runtime agêntico para geração e validação local de testes"
    )
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--artifacts-file", required=True)
    parser.add_argument("--base-sha", default=None)
    parser.add_argument("--head-sha", default=None)
    parser.add_argument("--run-state-dir", default=None)
    parser.add_argument(
        "--fail-on-escalation",
        action="store_true",
        help="Retorna código 1 se algum artefato exigir revisão humana.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_path = Path(args.repo_path).resolve()
    artifacts_path = Path(args.artifacts_file).resolve()
    artifacts = load_artifacts_from_json(artifacts_path)
    settings = get_settings()
    planner = PlannerCrewRunner(settings)
    state_dir = (
        Path(args.run_state_dir)
        if args.run_state_dir
        else artifacts_path.parent / "run_states" / "test_lifecycle"
    )
    executor = TestLifecycleCapabilityExecutor(
        settings=settings,
        repo_path=repo_path,
        base_sha=args.base_sha,
        head_sha=args.head_sha,
    )
    runtime = GovernedAgenticRuntime(
        orchestrator=executor,  # type: ignore[arg-type]
        state_store=JsonRunStateStore(state_dir),
    )

    started = time.perf_counter()
    escalated = 0
    eligible = 0

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
        print(f"\n🤖 Ciclo agêntico de testes: {artifact.file_path}")
        plan = planner.plan_test_lifecycle(artifact)
        artifact.add_policy(f"test_lifecycle_planner_{plan.planner_source}")
        artifact.add_note(f"Planner de testes: {plan.rationale}")
        state = runtime.run(artifact, plan)
        artifact.add_policy("governed_test_lifecycle")
        artifact.add_note(
            f"Ciclo de testes {state.run_id} finalizado como {state.status}."
        )
        if state.status == "ESCALATED":
            escalated += 1

    duration_ms = (time.perf_counter() - started) * 1000
    output_dir = str(artifacts_path.parent)
    export_artifacts_to_json(artifacts, output_dir)
    export_run_summary(artifacts, output_dir, duration_ms)

    print(
        f"\nCiclo concluído: {eligible} elegível(is), "
        f"{escalated} escalação(ões)."
    )
    if args.fail_on_escalation and escalated:
        sys.exit(1)


if __name__ == "__main__":
    main()
