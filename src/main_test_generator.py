import os
import time
from argparse import ArgumentParser
from pathlib import Path

from src.config.settings import get_settings
from src.crew.test_generator_crew import TestGeneratorCrewRunner
from src.crew.high_risk_strategy_crew import HighRiskTestStrategyRunner
from src.schemas.review_result import parse_review_markdown_to_review_result
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.services.analysis_orchestrator import AnalysisOrchestrator
from src.services.artifact_exporter import (
    export_artifacts_to_json,
    export_run_summary,
    load_artifacts_from_json,
)
from src.services.token_budget_planner import (
    TokenBudgetPlanner,
    build_code_content_for_plan,
)
from src.utils.git_utils import get_file_diff
from src.utils.pr_utils import (
    build_pr_body,
    create_branch_and_commit,
    get_current_branch,
    get_repo_full_name,
    open_pull_request,
    parse_test_files_from_output,
    push_branch,
    write_test_files,
)


def parse_args():
    parser = ArgumentParser(description="Agente gerador de testes unitários baseado no relatório de QA")

    parser.add_argument(
        "--repo-path",
        default=".",
        help="Caminho do repositório alvo",
    )

    parser.add_argument(
        "--report-file",
        default="outputs/analysis.md",
        help="Relatório Markdown legado, usado apenas se artifacts.json não existir",
    )

    parser.add_argument(
        "--artifacts-file",
        default=None,
        help=(
            "Handoff estruturado da análise. Padrão: artifacts.json no mesmo "
            "diretório de --report-file"
        ),
    )

    parser.add_argument(
        "--base-sha",
        default=None,
        help="Commit base para identificar arquivos alterados",
    )

    parser.add_argument(
        "--head-sha",
        default=None,
        help="Commit final para identificar arquivos alterados",
    )

    parser.add_argument(
        "--branch-prefix",
        default="qagent/tests",
        help="Prefixo da branch a ser criada",
    )

    parser.add_argument(
        "--base-branch",
        default=None,
        help="Branch base para o PR (padrão: branch atual)",
    )

    parser.add_argument(
        "--no-pr",
        action="store_true",
        help="Apenas gera os testes sem criar PR",
    )

    return parser.parse_args()


def read_report(report_file: str) -> str:
    path = Path(report_file)
    if not path.exists():
        raise FileNotFoundError(f"Relatório não encontrado: {report_file}")
    return path.read_text(encoding="utf-8")


def read_file_content(repo_path: Path, file_path: str) -> str:
    path = repo_path / file_path
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    return path.read_text(encoding="utf-8")


def extract_report_sections(full_report: str) -> dict[str, str]:
    """Divide o relatório completo em seções por arquivo analisado."""
    sections: dict[str, str] = {}
    parts = full_report.split("# Arquivo analisado: ")

    for part in parts[1:]:
        lines = part.strip().split("\n", 1)
        if lines:
            file_path = lines[0].strip()
            content = lines[1].strip() if len(lines) > 1 else ""
            sections[file_path] = content

    return sections


def render_report_from_artifacts(artifacts: list[FileAnalysisArtifact]) -> str:
    """Reconstrói o relatório agregado sem reinterpretar o Markdown."""
    sections = []
    for artifact in artifacts:
        review = artifact.raw_review_markdown or ""
        sections.append(f"# Arquivo analisado: {artifact.file_path}\n\n{review}")
    return "\n\n---\n\n".join(sections)


def build_legacy_artifacts(
    report_file: str,
    repo_path: Path,
    base_sha: str | None,
    head_sha: str | None,
    orchestrator: AnalysisOrchestrator,
    token_budget_planner: TokenBudgetPlanner,
) -> list[FileAnalysisArtifact]:
    """
    Compatibilidade com execuções antigas que produzem somente analysis.md.

    Este é o único caminho que reinterpreta Markdown e recalcula estratégia.
    """
    qa_report = read_report(report_file)
    report_sections = extract_report_sections(qa_report)
    artifacts: list[FileAnalysisArtifact] = []

    for file_path, section_report in report_sections.items():
        try:
            code_content = read_file_content(repo_path, file_path)
        except FileNotFoundError:
            continue

        file_diff = get_file_diff(
            file_path=file_path,
            repo_path=repo_path,
            base_sha=base_sha,
            head_sha=head_sha,
        )
        token_budget_plan = token_budget_planner.plan(
            file_path=file_path,
            file_diff=file_diff,
            code_content=code_content,
            cooperative_requested=False,
        )
        artifact = FileAnalysisArtifact(
            file_path=file_path,
            token_budget_plan=token_budget_plan,
            raw_review_markdown=section_report,
            review_result=parse_review_markdown_to_review_result(section_report),
        )
        artifact.mark_step_executed("parse_review_legacy")
        artifact.add_policy("legacy_markdown_handoff")
        artifact.add_policy(f"token_budget_{token_budget_plan.analysis_mode}")
        artifact.add_policy(f"context_{token_budget_plan.context_level}")
        artifact.add_note(token_budget_plan.reason)
        orchestrator.run_artifact_pipeline(artifact)
        artifacts.append(artifact)

    return artifacts


def load_generation_artifacts(
    artifacts_file: str | None,
    report_file: str,
    repo_path: Path,
    base_sha: str | None,
    head_sha: str | None,
    orchestrator: AnalysisOrchestrator,
    token_budget_planner: TokenBudgetPlanner,
) -> tuple[list[FileAnalysisArtifact], Path, bool]:
    """
    Carrega o contrato estruturado preferencialmente.

    Retorna artefatos, caminho de persistência e indicador de fallback legado.
    """
    handoff_path = (
        Path(artifacts_file)
        if artifacts_file
        else Path(report_file).parent / "artifacts.json"
    )

    if handoff_path.exists():
        return load_artifacts_from_json(handoff_path), handoff_path, False

    artifacts = build_legacy_artifacts(
        report_file=report_file,
        repo_path=repo_path,
        base_sha=base_sha,
        head_sha=head_sha,
        orchestrator=orchestrator,
        token_budget_planner=token_budget_planner,
    )
    return artifacts, handoff_path, True


def main() -> None:
    args = parse_args()
    repo_path = Path(args.repo_path).resolve()

    settings = get_settings()
    crew_runner = TestGeneratorCrewRunner(settings)
    high_risk_runner = HighRiskTestStrategyRunner(settings)
    orchestrator = AnalysisOrchestrator(high_risk_runner)
    token_budget_planner = TokenBudgetPlanner()

    artifacts, artifacts_handoff_path, used_legacy_handoff = load_generation_artifacts(
        artifacts_file=args.artifacts_file,
        report_file=args.report_file,
        repo_path=repo_path,
        base_sha=args.base_sha,
        head_sha=args.head_sha,
        orchestrator=orchestrator,
        token_budget_planner=token_budget_planner,
    )
    if not artifacts:
        print("Nenhum artefato de análise encontrado para geração de testes.")
        return

    if used_legacy_handoff:
        print("⚠️ artifacts.json ausente; usando handoff legado via analysis.md")
    else:
        print(f"📦 Handoff estruturado carregado de: {artifacts_handoff_path}")

    all_test_files: dict[str, str] = {}
    analyzed_files: list[str] = []
    pipeline_start = time.perf_counter()

    for artifact in artifacts:
        file_path = artifact.file_path
        print(f"\n🧪 Gerando testes para: {file_path}")

        try:
            code_content = read_file_content(repo_path, file_path)
        except FileNotFoundError:
            print(f"  ⚠️ Arquivo não encontrado no repo, pulando: {file_path}")
            continue

        file_diff = get_file_diff(
            file_path=file_path,
            repo_path=repo_path,
            base_sha=args.base_sha,
            head_sha=args.head_sha,
        )
        token_budget_plan = artifact.token_budget_plan
        if token_budget_plan is None:
            token_budget_plan = token_budget_planner.plan(
                file_path=file_path,
                file_diff=file_diff,
                code_content=code_content,
                cooperative_requested=False,
            )
            artifact.token_budget_plan = token_budget_plan
            artifact.add_fallback("missing_token_budget_plan")
            artifact.add_note(
                "TokenBudgetPlan ausente no handoff; plano recalculado na geração."
            )

        prompt_code_content = build_code_content_for_plan(
            code_content=code_content,
            file_diff=file_diff,
            plan=token_budget_plan,
        )

        print(f"  📊 Risco: {artifact.risk_level} | Review: {artifact.review_quality} | Testes: {artifact.test_generation_recommendation}")
        print(f"  ⏱️ Durações: {artifact.step_durations_ms}")

        if artifact.test_generation_recommendation == "SKIPPED":
            artifact.mark_step_skipped("test_generation", "sem testes recomendados")
            print(f"  ⏭️ Geração de testes pulada para: {file_path} (sem testes recomendados)")
            continue
        if artifact.review_result is None or artifact.test_strategy_result is None:
            artifact.mark_step_skipped(
                "test_generation",
                "handoff estruturado incompleto: review ou estratégia ausente",
            )
            artifact.add_fallback("incomplete_analysis_artifact")
            print(f"  ⚠️ Artefato incompleto para geração: {file_path}")
            continue

        t0 = time.perf_counter()
        result = crew_runner.run(
            qa_report=artifact.raw_review_markdown or "",
            file_path=file_path,
            code_content=prompt_code_content,
            repo_path=str(repo_path),
            test_strategy=artifact.test_strategy_result,
            review_result=artifact.review_result,
            token_budget_plan=token_budget_plan,
            risk_level=artifact.risk_level,
        )
        if artifact.context_result is None:
            artifact.context_result = crew_runner.last_context_result
        artifact.memory_query = crew_runner.last_memory_query
        artifact.memories_used_raw = crew_runner.last_memories_raw
        artifact.memories_used = crew_runner.last_memories_used
        artifact.record_duration("test_generation", (time.perf_counter() - t0) * 1000)
        artifact.mark_step_executed("test_generation")

        test_files = parse_test_files_from_output(result)

        if not test_files:
            artifact.add_note("Nenhum arquivo de teste extraído do output do agente")
            print(f"  ⚠️ Nenhum arquivo de teste extraído para: {file_path}")
            continue

        artifact.generated_tests_raw = result
        artifact.generated_test_files = test_files

        all_test_files.update(test_files)
        analyzed_files.append(file_path)

        for tf in test_files:
            print(f"  ✅ Teste gerado: {tf}")

    # Exportar artefatos estruturados
    if artifacts:
        output_dir = str(artifacts_handoff_path.parent)
        total_duration_ms = (time.perf_counter() - pipeline_start) * 1000
        artifacts_path = export_artifacts_to_json(artifacts, output_dir)
        summary_path = export_run_summary(artifacts, output_dir, total_duration_ms)
        print(f"\n📦 Artefatos: {artifacts_path}")
        print(f"📊 Resumo: {summary_path}")

    if not all_test_files:
        print("\n❌ Nenhum teste foi gerado.")
        return

    # Escreve os arquivos de teste no repositório
    created_files = write_test_files(repo_path, all_test_files)
    print(f"\n📁 {len(created_files)} arquivo(s) de teste criado(s)")

    if args.no_pr:
        print("\n✅ Testes gerados com sucesso (modo --no-pr, PR não criado)")
        return

    # Cria branch, commit, push e abre PR
    base_branch = args.base_branch or get_current_branch(repo_path)
    timestamp = int(time.time())
    branch_name = f"{args.branch_prefix}-{timestamp}"

    print(f"\n🌿 Criando branch: {branch_name}")
    create_branch_and_commit(
        repo_path=repo_path,
        branch_name=branch_name,
        test_files=created_files,
        commit_message=f"test: add unit tests generated by QAgent [skip-qagent]\n\nTests based on QA report for: {', '.join(analyzed_files)}",
    )

    print(f"🚀 Fazendo push para origin/{branch_name}")
    push_branch(repo_path, branch_name)

    github_token = os.getenv("GITHUB_TOKEN", "")
    if not github_token:
        print("\n⚠️ GITHUB_TOKEN não definido. Push realizado, mas PR não foi criado.")
        print(f"  Crie o PR manualmente da branch: {branch_name}")
        return

    repo_full_name = get_repo_full_name(repo_path)
    qa_report = render_report_from_artifacts(artifacts)
    pr_body = build_pr_body(qa_report, created_files, analyzed_files)

    pr_title = f"🧪 QAgent: Testes unitários para {', '.join(analyzed_files)}"
    if len(pr_title) > 120:
        pr_title = f"🧪 QAgent: Testes unitários para {len(analyzed_files)} arquivo(s)"

    print(f"\n📝 Abrindo PR em {repo_full_name}...")
    pr_url = open_pull_request(
        github_token=github_token,
        repo_full_name=repo_full_name,
        branch_name=branch_name,
        base_branch=base_branch,
        title=pr_title,
        body=pr_body,
    )

    print(f"\n✅ PR criado com sucesso: {pr_url}")

    # Salva o nome da branch para jobs subsequentes
    try:
        output_dir = artifacts_handoff_path.parent
        (output_dir / ".branch_name").write_text(branch_name, encoding="utf-8")
    except Exception as exc:
        print(f"⚠️ Não foi possível salvar o nome da branch: {exc}")


if __name__ == "__main__":
    main()
