from argparse import ArgumentParser
from pathlib import Path
import sys

from src.config.settings import get_settings
from src.services.agentic_coordinator import AgenticRepositoryCoordinator
from src.services.coordinator_state_store import JsonCoordinatorStateStore


def parse_args():
    parser = ArgumentParser(
        description="Coordinator agêntico persistente do QAgent"
    )
    parser.add_argument("--repo-path", default=".")
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--base-sha", default=None)
    parser.add_argument("--head-sha", default=None)
    parser.add_argument("--cooperative-analysis", action="store_true")
    parser.add_argument("--resume-run-id", default=None)
    parser.add_argument("--fail-on-escalation", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    coordinator = AgenticRepositoryCoordinator(
        get_settings(),
        state_store=JsonCoordinatorStateStore(
            output_dir / "coordinator_runs"
        ),
    )
    if args.resume_run_id:
        state = coordinator.resume(args.resume_run_id)
    else:
        state = coordinator.run(
            repo_path=args.repo_path,
            output_dir=output_dir,
            base_sha=args.base_sha,
            head_sha=args.head_sha,
            cooperative_analysis=args.cooperative_analysis,
        )

    print(f"Coordinator run: {state.run_id}")
    print(f"Status: {state.status}")
    print(f"Artefatos: {state.artifacts_file or 'não gerados'}")
    if args.fail_on_escalation and state.status in {"ESCALATED", "FAILED"}:
        sys.exit(1)


if __name__ == "__main__":
    main()
