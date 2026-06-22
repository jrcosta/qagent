from argparse import ArgumentParser
from pathlib import Path
import sys

from src.config.settings import get_settings
from src.services.artifact_exporter import load_artifacts_from_json
from src.services.test_lifecycle_pipeline import RepositoryTestLifecyclePipeline


def parse_args():
    parser = ArgumentParser(
        description="Runtime agêntico para geração e validação local de testes"
    )
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--artifacts-file", required=True)
    parser.add_argument("--base-sha", default=None)
    parser.add_argument("--head-sha", default=None)
    parser.add_argument("--run-state-dir", default=None)
    parser.add_argument("--fail-on-escalation", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifacts_path = Path(args.artifacts_file).resolve()
    result = RepositoryTestLifecyclePipeline(get_settings()).run(
        artifacts=load_artifacts_from_json(artifacts_path),
        repo_path=args.repo_path,
        output_dir=artifacts_path.parent,
        base_sha=args.base_sha,
        head_sha=args.head_sha,
        run_state_dir=args.run_state_dir,
    )
    print(
        f"Ciclo concluído: {result.eligible_files} elegível(is), "
        f"{result.escalated_files} escalação(ões)."
    )
    if args.fail_on_escalation and result.escalated_files:
        sys.exit(1)


if __name__ == "__main__":
    main()
