import json
import os
import sys
import time
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from src.config.settings import get_settings
from src.crew.test_reviewer_crew import TestReviewerCrewRunner
from src.crew.test_fixer_crew import TestFixerCrewRunner
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.schemas.test_strategy_result import render_test_strategy_result_for_prompt
from src.services.test_execution_runner import TestExecutionRunner
from src.utils.git_utils import get_file_diff
from src.utils.pr_utils import (
    add_pr_comment,
    get_repo_full_name,
    get_current_branch,
    parse_test_files_from_output,
    write_test_files,
    commit_and_push_to_branch,
)
from src.utils.review_comment_utils import build_test_review_comment, review_result_to_finding


def parse_args():
    parser = ArgumentParser(description="Agente de revisão crítica de testes gerados")

    parser.add_argument(
        "--repo-path",
        required=True,
        help="Caminho do repositório alvo",
    )

    parser.add_argument(
        "--artifacts-file",
        required=True,
        help="Caminho do arquivo artifacts.json",
    )

    parser.add_argument(
        "--pr-url",
        required=False,
        help="URL do PR aberto (opcional, tenta inferir se não fornecido)",
    )

    parser.add_argument(
        "--branch-name",
        required=False,
        help="Nome da branch do PR (usado para localizar o PR)",
    )

    parser.add_argument(
        "--base-sha",
        default=None,
        help="Commit base para contextualizar o diff revisado",
    )

    parser.add_argument(
        "--head-sha",
        default=None,
        help="Commit final para contextualizar o diff revisado",
    )

    parser.add_argument(
        "--execute-tests",
        action="store_true",
        help="Executa a suíte de testes do repositório alvo e usa o resultado real como contexto da revisão",
    )

    parser.add_argument(
        "--fail-on-test-execution",
        action="store_true",
        help="Encerra com erro quando a execução real dos testes falhar",
    )

    parser.add_argument(
        "--auto-fix-tests",
        action="store_true",
        help="Tenta corrigir automaticamente os testes que falharam na revisão",
    )

    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Encerra com erro quando a revisão encontrar NEEDS_CHANGES ou INVALID",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_path = Path(args.repo_path).resolve()
    artifacts_path = Path(args.artifacts_file).resolve()

    if not artifacts_path.exists():
        print(f"❌ Arquivo de artefatos não encontrado: {artifacts_path}")
        return

    with open(artifacts_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    artifacts = [FileAnalysisArtifact(**a) for a in data]

    # Filtra apenas artefatos que tiveram testes gerados.
    test_artifacts = [a for a in artifacts if "test_generation" in a.executed_steps]

    if not test_artifacts:
        print("ℹ️ Nenhum artefato com testes gerados encontrado para revisão.")
        return

    execution_failed = False

    if args.execute_tests:
        print("\n🧪 Executando testes reais no repositório alvo...")
        t0 = time.perf_counter()
        execution_result = TestExecutionRunner(repo_path=str(repo_path)).run()
        execution_duration_ms = (time.perf_counter() - t0) * 1000
        execution_failed = not execution_result.success

        status_icon = "✅" if execution_result.success else "❌"
        print(
            f"{status_icon} Execução finalizada com exit_code={execution_result.exit_code} "
            f"em {execution_result.duration_seconds:.2f}s"
        )

        for artifact in test_artifacts:
            artifact.test_execution_result = execution_result
            artifact.record_duration("test_execution", execution_duration_ms)
            artifact.mark_step_executed("test_execution")
            artifact.add_note(
                "Execução real dos testes concluída com sucesso."
                if execution_result.success
                else "Execução real dos testes falhou; saída anexada ao contexto da revisão crítica."
            )
    else:
        for artifact in test_artifacts:
            artifact.mark_step_skipped("test_execution", "flag --execute-tests não informado")

    settings = get_settings()
    reviewer_runner = TestReviewerCrewRunner(settings)
    fixer_runner = TestFixerCrewRunner(settings)

    all_findings = []
    artifacts_needing_fix = []

    for artifact in test_artifacts:
        print(f"\n🔍 Revisando criticamente: {artifact.file_path}")

        # Lê o código fonte original.
        code_path = repo_path / artifact.file_path
        if not code_path.exists():
            print(f"  ⚠️ Código fonte não encontrado: {code_path}")
            artifact.mark_step_skipped("test_review", "código fonte não encontrado")
            continue

        code_content = code_path.read_text(encoding="utf-8")

        # Recupera o report de QA original do artefato.
        qa_report = artifact.raw_review_markdown or ""
        if artifact.test_execution_result:
            qa_report = (
                qa_report
                + "\n\n---\n\n"
                + "## Resultado real da execução dos testes\n\n"
                + _render_execution_result_for_prompt(artifact.test_execution_result)
            )

        generated_tests = artifact.generated_tests_raw or _render_generated_test_files(
            artifact.generated_test_files
        )
        if not generated_tests:
            print("  ⚠️ Testes gerados não encontrados no artefato. Pulando.")
            artifact.mark_step_skipped("test_review", "testes gerados não encontrados")
            continue

        file_diff = get_file_diff(
            file_path=artifact.file_path,
            repo_path=repo_path,
            base_sha=args.base_sha,
            head_sha=args.head_sha,
        )
        if artifact.test_strategy_result:
            test_strategy = render_test_strategy_result_for_prompt(artifact.test_strategy_result)
        else:
            test_strategy = "Nenhuma recomendação de teste disponível na estratégia."

        t0 = time.perf_counter()
        review_result = reviewer_runner.run(
            file_path=artifact.file_path,
            code_content=code_content,
            qa_report=qa_report,
            test_strategy=test_strategy,
            generated_tests=generated_tests,
            file_diff=file_diff,
        )
        artifact.generated_test_review_result = review_result
        artifact.record_duration("test_review", (time.perf_counter() - t0) * 1000)
        artifact.mark_step_executed("test_review")

        print(f"  📝 Status da Revisão: {review_result.status}")
        if review_result.issues:
            print(f"  ⚠️ {len(review_result.issues)} problema(s) identificado(s).")
            if review_result.status in ["NEEDS_CHANGES", "INVALID"]:
                artifacts_needing_fix.append(artifact)

        finding = review_result_to_finding(artifact.file_path, review_result)
        if finding:
            all_findings.append(finding)

    # Lógica de AUTO-FIX
    if args.auto_fix_tests and artifacts_needing_fix:
        print(f"\n🛠️ Iniciando correção automática para {len(artifacts_needing_fix)} arquivo(s)...")
        all_fixed_files = {}
        
        for artifact in artifacts_needing_fix:
            print(f"  🔧 Corrigindo testes para: {artifact.file_path}")
            
            code_path = repo_path / artifact.file_path
            code_content = code_path.read_text(encoding="utf-8")
            
            if artifact.test_strategy_result:
                test_strategy = render_test_strategy_result_for_prompt(artifact.test_strategy_result)
            else:
                test_strategy = "Nenhuma estratégia disponível."

            failed_tests = artifact.generated_tests_raw or _render_generated_test_files(artifact.generated_test_files)
            review_report = f"STATUS: {artifact.generated_test_review_result.status}\n\n"
            review_report += f"SUMMARY: {artifact.generated_test_review_result.summary}\n\n"
            review_report += "ISSUES:\n"
            for issue in artifact.generated_test_review_result.issues:
                review_report += f"- [{issue.severity}] {issue.description} (Fix: {issue.suggest_fix or 'N/A'})\n"

            t0 = time.perf_counter()
            fixed_output = fixer_runner.run(
                file_path=artifact.file_path,
                code_content=code_content,
                test_strategy=test_strategy,
                failed_tests=failed_tests,
                review_report=review_report
            )
            
            fixed_files = parse_test_files_from_output(fixed_output)
            if fixed_files:
                artifact.generated_tests_raw = fixed_output
                artifact.generated_test_files = fixed_files
                artifact.record_duration("test_auto_fix", (time.perf_counter() - t0) * 1000)
                artifact.mark_step_executed("test_auto_fix")
                artifact.add_note("Testes corrigidos automaticamente após revisão crítica.")
                all_fixed_files.update(fixed_files)
                print(f"    ✅ {len(fixed_files)} arquivo(s) corrigido(s).")
            else:
                print(f"    ❌ Falha ao extrair testes corrigidos para {artifact.file_path}")

        if all_fixed_files:
            print("\n💾 Salvando arquivos corrigidos e enviando para o repositório...")
            created_files = write_test_files(repo_path, all_fixed_files)
            
            repo_full_name = get_repo_full_name(repo_path)
            branch_name = args.branch_name
            if not branch_name:
                branch_name_file = artifacts_path.parent / ".branch_name"
                if branch_name_file.exists():
                    branch_name = branch_name_file.read_text(encoding="utf-8").strip()
            
            if not branch_name:
                branch_name = get_current_branch(repo_path)
            
            try:
                commit_and_push_to_branch(
                    repo_path=repo_path,
                    branch_name=branch_name,
                    files=created_files,
                    commit_message=f"fix(tests): auto-fix {len(created_files)} test files after QAgent review"
                )
                print(f"✅ {len(created_files)} arquivo(s) de teste atualizados na branch {branch_name}")
            except Exception as e:
                print(f"❌ Erro ao enviar correções para o git: {e}")

    _save_artifacts(artifacts_path, artifacts)
    print(f"\n💾 Artefatos atualizados em: {artifacts_path}")

    if not all_findings:
        print("\n✅ Todos os testes foram aprovados na revisão crítica.")
    else:
        print(f"\n⚠️ {len(all_findings)} arquivo(s) com ressalvas na revisão.")

    summary_comment = build_test_review_comment(all_findings)

    # Postar comentário no PR.
    github_token = os.getenv("GITHUB_TOKEN", "")
    if not github_token:
        print("\n⚠️ GITHUB_TOKEN não definido. Não foi possível postar o comentário no PR.")
        _exit_if_needed(args, all_findings, execution_failed)
        return

    repo_full_name = get_repo_full_name(repo_path)

    # Tenta obter o nome da branch do arquivo salvo pelo generator.
    branch_name = args.branch_name
    if not branch_name:
        branch_name_file = artifacts_path.parent / ".branch_name"
        if branch_name_file.exists():
            branch_name = branch_name_file.read_text(encoding="utf-8").strip()
            print(f"🌿 Usando branch detectada: {branch_name}")

    if not branch_name:
        branch_name = get_current_branch(repo_path)

    try:
        add_pr_comment(
            github_token=github_token,
            repo_full_name=repo_full_name,
            branch_name=branch_name,
            comment_body=summary_comment,
        )
        print(f"\n💬 Resultado da revisão postado como comentário no PR (branch: {branch_name}).")
    except Exception as exc:
        print(f"\n⚠️ Erro ao postar comentário no PR: {exc}")

    _exit_if_needed(args, all_findings, execution_failed)


def _exit_if_needed(args: Any, all_findings: list, execution_failed: bool) -> None:
    if args.fail_on_test_execution and execution_failed:
        print(
            "\n❌ Execução real dos testes falhou. "
            "Bloqueando o merge via status check."
        )
        sys.exit(1)

    if args.fail_on_findings and all_findings:
        # Se for AUTO-FIX, talvez não queiramos falhar se o fix funcionou?
        # Mas aqui o 'all_findings' ainda reflete a revisão ORIGINAL.
        # Por simplicidade, mantemos o comportamento de falha se houve qualquer finding.
        print(
            "\n❌ Revisão crítica encontrou problemas nos testes gerados. "
            "Bloqueando o merge via status check."
        )
        sys.exit(1)


def _render_execution_result_for_prompt(execution_result) -> str:
    stdout = _truncate_text(execution_result.stdout or "", limit=6000)
    stderr = _truncate_text(execution_result.stderr or "", limit=6000)

    return (
        f"- success: {execution_result.success}\n"
        f"- command: `{execution_result.command}`\n"
        f"- exit_code: {execution_result.exit_code}\n"
        f"- duration_seconds: {execution_result.duration_seconds:.2f}\n\n"
        f"### stdout\n```text\n{stdout}\n```\n\n"
        f"### stderr\n```text\n{stderr}\n```"
    )


def _truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "\n... [conteúdo truncado para caber no prompt]"


def _save_artifacts(artifacts_path: Path, artifacts: list[FileAnalysisArtifact]) -> None:
    serialized = []
    for artifact in artifacts:
        if hasattr(artifact, "model_dump"):
            serialized.append(artifact.model_dump(mode="json"))
        else:
            serialized.append(artifact.dict())

    artifacts_path.write_text(
        json.dumps(serialized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _render_generated_test_files(test_files: dict[str, str]) -> str:
    if not test_files:
        return ""

    sections = []
    for file_path, content in test_files.items():
        sections.append(f"### FILE: {file_path}\n```\n{content}\n```")
    return "\n\n".join(sections)


if __name__ == "__main__":
    main()
