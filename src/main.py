from argparse import ArgumentParser
from pathlib import Path
import time

from src.config.settings import get_settings
from src.crew.qa_crew import QACrewRunner
from src.crew.high_risk_strategy_crew import HighRiskTestStrategyRunner
from src.utils.git_utils import get_changed_files, get_file_diff
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.services.analysis_orchestrator import AnalysisOrchestrator
from src.services.artifact_exporter import export_artifacts_to_json, export_run_summary


def parse_args():
    parser = ArgumentParser()

    parser.add_argument(
        "--repo-path",
        default=".",
        help="Caminho do repositório a ser analisado",
    )

    parser.add_argument(
        "--output-file",
        default="outputs/analysis.md",
        help="Arquivo de saída do relatório",
    )

    parser.add_argument(
        "--base-sha",
        default=None,
        help="Commit base para comparação",
    )

    parser.add_argument(
        "--head-sha",
        default=None,
        help="Commit final para comparação",
    )

    return parser.parse_args()


def read_file_content(repo_path: Path, file_path: str) -> str:
    path = repo_path / file_path

    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    return path.read_text(encoding="utf-8")


def save_output(content: str, output_file: str) -> None:
    output_path = Path(output_file)
    output_path.parent.mkdir(exist_ok=True, parents=True)
    output_path.write_text(content, encoding="utf-8")


def build_report(sections: list[str]) -> str:
    return "\n\n---\n\n".join(sections)


def main() -> None:
    args = parse_args()
    repo_path = Path(args.repo_path).resolve()
    pipeline_start = time.perf_counter()

    settings = get_settings()
    crew_runner = QACrewRunner(settings)
    high_risk_runner = HighRiskTestStrategyRunner(settings)
    orchestrator = AnalysisOrchestrator(high_risk_runner)

    changed_files = get_changed_files(
        repo_path=repo_path,
        base_sha=args.base_sha,
        head_sha=args.head_sha,
    )

    if not changed_files:
        message = "# Nenhum arquivo alterado relevante encontrado para análise."
        save_output(message, args.output_file)
        print(message)
        return

    analyses = []
    artifacts: list[FileAnalysisArtifact] = []

    for file_path in changed_files:
        print(f"Analisando: {file_path}")

        code_content = read_file_content(repo_path, file_path)
        file_diff = get_file_diff(
            file_path=file_path,
            repo_path=repo_path,
            base_sha=args.base_sha,
            head_sha=args.head_sha,
        )

        if not file_diff.strip():
            print(f"Sem diff relevante para: {file_path}")
            continue

        # --- QA Review ---
        t0 = time.perf_counter()
        crew_result = crew_runner.run(
            file_path=file_path,
            file_diff=file_diff,
            code_content=code_content,
            repo_path=str(repo_path),
        )
        qa_duration = (time.perf_counter() - t0) * 1000

        # 1. Monta artefato parcial e avalia risco
        artifact = FileAnalysisArtifact(
            file_path=file_path,
            raw_review_markdown=crew_result.raw_review_markdown,
            review_result=crew_result.review_result,
        )
        artifact.mark_step_executed("qa_review")
        artifact.record_duration("qa_review", qa_duration)

        # --- Pipeline de avaliação e estratégia ---
        orchestrator.run_artifact_pipeline(artifact)
        artifacts.append(artifact)

        print(f"  📊 Risco: {artifact.risk_level} | Review: {artifact.review_quality} | Testes: {artifact.test_generation_recommendation}")
        print(f"  ⏱️ Durações: {artifact.step_durations_ms}")

        section = f"# Arquivo analisado: {file_path}\n\n{artifact.raw_review_markdown}"
        analyses.append(section)

    if not analyses:
        message = "# Nenhum diff relevante encontrado para análise."
        save_output(message, args.output_file)
        print(message)
        return

    final_report = build_report(analyses)
    save_output(final_report, args.output_file)

    # Exportar artefatos estruturados
    output_dir = str(Path(args.output_file).parent)
    total_duration_ms = (time.perf_counter() - pipeline_start) * 1000

    artifacts_path = export_artifacts_to_json(artifacts, output_dir)
    summary_path = export_run_summary(artifacts, output_dir, total_duration_ms)

    print("\nAnálise salva em:")
    print(args.output_file)
    print(f"📦 Artefatos: {artifacts_path}")
    print(f"📊 Resumo: {summary_path}")


if __name__ == "__main__":
    main()