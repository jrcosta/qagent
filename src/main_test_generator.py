import os
import time
from argparse import ArgumentParser
from pathlib import Path

from src.config.settings import get_settings
from src.crew.test_generator_crew import TestGeneratorCrewRunner
from src.crew.high_risk_strategy_crew import HighRiskTestStrategyRunner
from src.crew.test_reviewer_crew import TestReviewerCrewRunner
from src.utils.git_utils import get_changed_files, get_file_diff
from src.schemas.review_result import parse_review_markdown_to_review_result
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.services.analysis_orchestrator import AnalysisOrchestrator
from src.schemas.test_strategy_result import render_test_strategy_result_for_prompt
from src.services.artifact_exporter import export_artifacts_to_json, export_run_summary
from src.utils.pr_utils import (
    build_pr_body,
    create_branch_and_commit,
    get_current_branch,
    get_repo_full_name,
    open_pull_request,
    add_pr_comment,
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
        help="Caminho do relatório de QA gerado pelo primeiro agente",
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


def main() -> None:
    args = parse_args()
    repo_path = Path(args.repo_path).resolve()

    settings = get_settings()
    crew_runner = TestGeneratorCrewRunner(settings)
    high_risk_runner = HighRiskTestStrategyRunner(settings)
    reviewer_runner = TestReviewerCrewRunner(settings)
    orchestrator = AnalysisOrchestrator(high_risk_runner)

    qa_report = read_report(args.report_file)
    report_sections = extract_report_sections(qa_report)

    if not report_sections:
        print("Nenhuma seção de arquivo encontrada no relatório de QA.")
        return

    changed_files = list(report_sections.keys())

    file_to_tests: dict[str, dict[str, str]] = {}
    analyzed_files: list[str] = []
    artifacts: list[FileAnalysisArtifact] = []
    pipeline_start = time.perf_counter()

    for file_path in changed_files:
        print(f"\n🧪 Gerando testes para: {file_path}")

        try:
            code_content = read_file_content(repo_path, file_path)
        except FileNotFoundError:
            print(f"  ⚠️ Arquivo não encontrado no repo, pulando: {file_path}")
            continue

        section_report = report_sections[file_path]

        # Gera ReviewResult estruturado a partir do markdown de QA
        review_result = parse_review_markdown_to_review_result(section_report)

        # 1. Monta artefato parcial e avalia risco
        artifact = FileAnalysisArtifact(
            file_path=file_path,
            raw_review_markdown=section_report,
            review_result=review_result,
        )
        artifact.mark_step_executed("parse_review")

        # --- Pipeline de avaliação e estratégia ---
        orchestrator.run_artifact_pipeline(artifact)

        print(f"  📊 Risco: {artifact.risk_level} | Review: {artifact.review_quality} | Testes: {artifact.test_generation_recommendation}")
        print(f"  ⏱️ Durações: {artifact.step_durations_ms}")

        if artifact.test_generation_recommendation == "SKIPPED":
            artifact.mark_step_skipped("test_generation", "sem testes recomendados")
            print(f"  ⏭️ Geração de testes pulada para: {file_path} (sem testes recomendados)")
            continue

        t0 = time.perf_counter()
        result = crew_runner.run(
            qa_report=section_report,
            file_path=file_path,
            code_content=code_content,
            repo_path=str(repo_path),
            test_strategy=artifact.test_strategy_result,
        )
        artifact.record_duration("test_generation", (time.perf_counter() - t0) * 1000)
        artifact.mark_step_executed("test_generation")

        test_files = parse_test_files_from_output(result)

        if not test_files:
            artifact.add_note("Nenhum arquivo de teste extraído do output do agente")
            print(f"  ⚠️ Nenhum arquivo de teste extraído para: {file_path}")
            continue

        # --- Stage: Revisão Crítica dos Testes Gerados ---
        print(f"  🔍 Revisando criticamente os testes para: {file_path}")
        t0_review = time.perf_counter()
        try:
            file_diff = get_file_diff(
                file_path=file_path,
                repo_path=repo_path,
                base_sha=args.base_sha,
                head_sha=args.head_sha,
            )

            review_result = reviewer_runner.run(
                file_path=file_path,
                code_content=code_content,
                qa_report=section_report,
                test_strategy=render_test_strategy_result_for_prompt(artifact.test_strategy_result),
                generated_tests=result,
                file_diff=file_diff,
            )
            artifact.generated_test_review_result = review_result
            artifact.record_duration("test_review", (time.perf_counter() - t0_review) * 1000)
            artifact.mark_step_executed("test_review")

            print(f"  📝 Status da Revisão: {review_result.status}")
            if review_result.issues:
                print(f"  ⚠️ {len(review_result.issues)} problema(s) identificado(s) na revisão.")
        except Exception as exc:
            artifact.add_fallback(f"test_review_failed: {str(exc)}")
            print(f"  ❌ Erro durante a revisão dos testes: {exc}")

        # Guardamos os testes vinculados ao arquivo original para o batching
        file_to_tests[file_path] = test_files
        analyzed_files.append(file_path)

        for tf in test_files:
            print(f"  ✅ Teste gerado: {tf}")

        artifacts.append(artifact)

    # Exportar artefatos estruturados
    if artifacts:
        output_dir = str(Path(args.report_file).parent)
        total_duration_ms = (time.perf_counter() - pipeline_start) * 1000
        export_artifacts_to_json(artifacts, output_dir)
        export_run_summary(artifacts, output_dir, total_duration_ms)

    if not file_to_tests:
        print("\n❌ Nenhum teste foi gerado.")
        return

    # Escreve os arquivos de teste no repositório
    created_files = write_test_files(repo_path, all_test_files)
    print(f"\n📁 {len(created_files)} arquivo(s) de teste criado(s)")

    if args.no_pr:
        print("\n✅ Testes gerados com sucesso (modo --no-pr, PR não criado)")
        return

    # --- Geração de PRs Inteligente (Batching) ---
    # REGRA DE NEGÓCIO: O GitHub limita o corpo do PR a 65.536 caracteres (Erro 422).
    # Para garantir que o relatório de QA (que pode ser gigante) seja entregue sem cortes,
    # dividimos a execução em lotes. O primeiro lote cria o PR e os demais adicionam
    # commits e postam suas seções do relatório como COMENTÁRIOS, que possuem seu próprio limite de 65k.
    BATCH_SIZE = 3 
    batches = [artifacts[i:i + BATCH_SIZE] for i in range(0, len(artifacts), BATCH_SIZE)]
    
    print(f"\n📦 Total de arquivos com testes: {len(artifacts)} | Dividindo em {len(batches)} lote(s) de commits")

    base_branch = args.base_branch or get_current_branch(repo_path)
    github_token = os.getenv("GITHUB_TOKEN", "")
    repo_full_name = get_repo_full_name(repo_path)
    
    timestamp = int(time.time())
    branch_name = f"{args.branch_prefix}-{timestamp}"
    pr_url = None

    for idx, batch in enumerate(batches):
        print(f"\n🚀 Processando Lote {idx + 1}/{len(batches)}...")
        
        batch_analyzed_files = [art.file_path for art in batch]
        batch_test_files_dict = {}
        batch_report_content = []
        
        for art in batch:
            tests = file_to_tests.get(art.file_path, {})
            batch_test_files_dict.update(tests)
            batch_report_content.append(f"# Arquivo analisado: {art.file_path}\n\n{art.raw_review_markdown}")
            
        # 1. Escreve os arquivos deste lote no disco
        created_test_paths = write_test_files(repo_path, batch_test_files_dict)
        
        # 2. Commit (na mesma branch para todos os lotes)
        if idx == 0:
            print(f"  🌿 Criando branch: {branch_name}")
            create_branch_and_commit(
                repo_path=repo_path,
                branch_name=branch_name,
                test_files=created_test_paths,
                commit_message=f"test: add unit tests batch {idx + 1} [skip-qagent]\n\nTests for: {', '.join(batch_analyzed_files)}",
            )
        else:
            # Apenas adiciona e comita na branch atual
            print(f"  📝 Adicionando commits ao lote {idx + 1}...")
            for f in created_test_paths:
                run_git(["add", f], repo_path)
            run_git(["commit", "-m", f"test: add unit tests batch {idx + 1} [skip-qagent]"], repo_path)
        
        # 3. Push
        print(f"  📤 Fazendo push para origin/{branch_name}...")
        push_branch(repo_path, branch_name)
        
        # 4. PR ou Comentário
        if github_token:
            relevant_report = "\n\n---\n\n".join(batch_report_content)
            
            if idx == 0:
                # Primeiro lote: Cria o PR
                pr_body = build_pr_body(relevant_report, created_test_paths, batch_analyzed_files)
                print(f"  📝 Abrindo PR em {repo_full_name}...")
                try:
                    pr_url = open_pull_request(
                        github_token=github_token,
                        repo_full_name=repo_full_name,
                        branch_name=branch_name,
                        base_branch=base_branch,
                        title=f"🧪 QAgent: Testes unitários para {len(artifacts)} arquivo(s)",
                        body=pr_body,
                    )
                    print(f"  ✅ PR criado: {pr_url}")
                except Exception as e:
                    print(f"  ❌ Erro ao criar PR: {e}")
            else:
                # Lotes subsequentes: Adiciona comentário ao PR
                print(f"  💬 Adicionando relatório do lote {idx + 1} como comentário no PR...")
                comment_body = f"### 🧪 Relatório de QA - Lote {idx + 1}\n\n{relevant_report}"
                try:
                    add_pr_comment(
                        github_token=github_token,
                        repo_full_name=repo_full_name,
                        branch_name=branch_name,
                        comment_body=comment_body,
                    )
                    print(f"  ✅ Comentário adicionado.")
                except Exception as e:
                    print(f"  ⚠️ Erro ao adicionar comentário: {e}")
        else:
            print(f"  ⚠️ GITHUB_TOKEN não definido.")
            
    print(f"\n✅ Todos os lotes foram processados e enviados para o PR.")
        
    print(f"\n✅ Processamento de todos os lotes finalizado.")

    # Salva o nome da branch para jobs subsequentes
    try:
        output_dir = Path(args.report_file).parent
        (output_dir / ".branch_name").write_text(branch_name, encoding="utf-8")
    except Exception as exc:
        print(f"⚠️ Não foi possível salvar o nome da branch: {exc}")


if __name__ == "__main__":
    main()
