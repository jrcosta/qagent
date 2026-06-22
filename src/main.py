from argparse import ArgumentParser
from pathlib import Path

from src.config.settings import get_settings
from src.services.analysis_pipeline import RepositoryAnalysisPipeline


def parse_args():
    parser = ArgumentParser()
    parser.add_argument("--repo-path", default=".")
    parser.add_argument("--output-file", default="outputs/analysis.md")
    parser.add_argument("--base-sha", default=None)
    parser.add_argument("--head-sha", default=None)
    parser.add_argument("--cooperative-analysis", action="store_true")
    parser.add_argument("--agentic-runtime", action="store_true")
    parser.add_argument("--run-state-dir", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = RepositoryAnalysisPipeline(get_settings()).run(
        repo_path=args.repo_path,
        output_file=args.output_file,
        base_sha=args.base_sha,
        head_sha=args.head_sha,
        cooperative_analysis=args.cooperative_analysis,
        agentic_runtime=args.agentic_runtime,
        run_state_dir=args.run_state_dir,
    )
    print(f"Análise salva em: {result.report_file}")
    print(f"Artefatos: {result.artifacts_file}")
    print(f"Resumo: {result.summary_file}")


if __name__ == "__main__":
    main()
