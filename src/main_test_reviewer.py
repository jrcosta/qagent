import json
import os
import subprocess
import sys
import time
from argparse import ArgumentParser
from pathlib import Path

from src.config.settings import get_settings
from src.crew.test_fixer_crew import TestFixerCrewRunner
from src.crew.test_reviewer_crew import TestReviewerCrewRunner
from src.schemas.generated_test_review_result import GeneratedTestsReviewResult
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.schemas.test_strategy_result import render_test_strategy_result_for_prompt
from src.services.ci_failure_collector import CIFailureCollector, render_ci_result_for_prompt
from src.utils.git_utils import get_file_diff
from src.utils.pr_utils import (
    add_pr_comment,
    get_repo_full_name,
    get_current_branch,
    parse_test_files_from_output,
    run_git,
    write_test_files,
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
        "--fail-on-findings",
        action="store_true",
        help="Encerra com erro quando a revisão encontrar NEEDS_CHANGES ou INVALID",
    )

    parser.add_argument(
        "--ci-check-timeout-seconds",
        type=int,
        default=180,
        help="Tempo máximo para aguardar checks de CI do PR alvo antes da revisão",
    )

    parser.add_argument(
        "--auto-fix-tests",
        action="store_true",
        help="Aciona um agente corretor para atualizar testes gerados e fazer push na mesma branch do PR",
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
    
    # Filtra apenas artefatos que tiveram testes gerados
    test_artifacts = [a for a in artifacts if "test_generation" in a.executed_steps]

    if not test_artifacts:
        print("ℹ️ Nenhum artefato com testes gerados encontrado para revisão.")
        return

    settings = get_settings()
    reviewer_runner = TestReviewerCrewRunner(settings)
    fixer_runner = TestFixerCrewRunner(settings)

    repo_full_name = get_repo_full_name(repo_path)
    branch_name = args.branch_name
    if not branch_name:
        branch_name_file = artifacts_path.parent / ".branch_name"
        if branch_name_file.exists():
            branch_name = branch_name_file.read_text(encoding="utf-8").strip()
            print(f"🌿 Usando branch detectada: {branch_name}")

    if not branch_name:
        branch_name = get_current_branch(repo_path)

    print("\n🧪 Consultando CI do PR alvo antes da revisão crítica...")
    ci_result = CIFailureCollector(
        repo_path=repo_path,
        repo_full_name=repo_full_name,
        branch_name=branch_name,
        pr_url=args.pr_url or "",
        timeout_seconds=args.ci_check_timeout_seconds,
    ).collect()
    ci_execution_summary = render_ci_result_for_prompt(ci_result)
    print(f"  CI: {ci_result.status} | {ci_result.summary.splitlines()[0]}")
    
    all_findings = []
    fixed_files: list[str] = []

    for artifact in test_artifacts:
        print(f"\n🔍 Revisando criticamente: {artifact.file_path}")
        
        # Lê o código fonte original
        code_path = repo_path / artifact.file_path
        if not code_path.exists():
            print(f"  ⚠️ Código fonte não encontrado: {code_path}")
            continue
        
        code_content = code_path.read_text(encoding="utf-8")
        
        # Recupera o report de QA original do artefato
        qa_report = artifact.raw_review_markdown or ""

        generated_tests = artifact.generated_tests_raw or _render_generated_test_files(
            artifact.generated_test_files
        )
        if not generated_tests:
            print("  ⚠️ Testes gerados não encontrados no artefato. Pulando.")
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
            ci_execution_summary=ci_execution_summary,
        )
        artifact.generated_test_review_result = review_result
        artifact.record_duration("test_review", (time.perf_counter() - t0) * 1000)
        artifact.mark_step_executed("ci_test_validation")
        artifact.mark_step_executed("test_review")
        artifact.add_policy(f"ci_validation_{ci_result.status}")
        artifact.add_note(ci_result.summary)

        print(f"  📝 Status da Revisão: {review_result.status}")
        if review_result.issues:
            print(f"  ⚠️ {len(review_result.issues)} problema(s) identificado(s).")

        finding = review_result_to_finding(artifact.file_path, review_result)
        if finding:
            all_findings.append(finding)

        if args.auto_fix_tests and finding and ci_result.status == "failed":
            print(f"  🛠️ Acionando corretor de testes para: {artifact.file_path}")
            fixed_files.extend(
                _run_test_fixer(
                    fixer_runner=fixer_runner,
                    repo_path=repo_path,
                    artifact=artifact,
                    code_content=code_content,
                    generated_tests=generated_tests,
                    review_result=review_result,
                    ci_execution_summary=ci_execution_summary,
                )
            )

    if fixed_files:
        _commit_and_push_test_fixes(repo_path, branch_name, fixed_files)
        print(
            "\n🛠️ Correções de testes enviadas para a mesma branch do PR: "
            f"{branch_name}"
        )

    if not all_findings:
        print("\n✅ Todos os testes foram aprovados na revisão crítica.")
    else:
        print(f"\n⚠️ {len(all_findings)} arquivo(s) com ressalvas na revisão.")

    summary_comment = build_test_review_comment(all_findings)

    # Postar comentário no PR
    github_token = os.getenv("GITHUB_TOKEN", "")
    if not github_token:
        print("\n⚠️ GITHUB_TOKEN não definido. Não foi possível postar o comentário no PR.")
        return

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

    if args.fail_on_findings and all_findings:
        print(
            "\n❌ Revisão crítica encontrou problemas nos testes gerados. "
            "Bloqueando o merge via status check."
        )
        sys.exit(1)


def _render_generated_test_files(test_files: dict[str, str]) -> str:
    if not test_files:
        return ""

    sections = []
    for file_path, content in test_files.items():
        sections.append(f"### FILE: {file_path}\n```\n{content}\n```")
    return "\n\n".join(sections)


def _run_test_fixer(
    fixer_runner: TestFixerCrewRunner,
    repo_path: Path,
    artifact: FileAnalysisArtifact,
    code_content: str,
    generated_tests: str,
    review_result: GeneratedTestsReviewResult,
    ci_execution_summary: str,
) -> list[str]:
    raw_fix = fixer_runner.run(
        file_path=artifact.file_path,
        code_content=code_content,
        generated_tests=generated_tests,
        review_summary=_render_review_result_for_fixer(review_result),
        ci_execution_summary=ci_execution_summary,
    )
    test_files = parse_test_files_from_output(raw_fix)
    test_files = _filter_test_file_paths(test_files)
    if not test_files:
        artifact.add_note("Test fixer não retornou arquivos corrigidos em formato FILE.")
        print("  ⚠️ Corretor não retornou arquivos de teste válidos.")
        return []

    fixed_files = write_test_files(repo_path, test_files)
    artifact.mark_step_executed("test_fix")
    artifact.add_policy("test_fixer_ci_based")
    return fixed_files


def _filter_test_file_paths(test_files: dict[str, str]) -> dict[str, str]:
    return {
        path: content
        for path, content in test_files.items()
        if _looks_like_test_file(path)
    }


def _looks_like_test_file(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    file_name = Path(normalized).name
    return (
        "/test/" in normalized
        or "/tests/" in normalized
        or "/__tests__/" in normalized
        or file_name.startswith("test_")
        or file_name.endswith("_test.py")
        or ".test." in file_name
        or ".spec." in file_name
        or file_name.endswith("test.java")
        or file_name.endswith("tests.java")
    )


def _render_review_result_for_fixer(review_result: GeneratedTestsReviewResult) -> str:
    lines = [
        f"Status: {review_result.status}",
        f"Resumo: {review_result.summary}",
    ]
    if review_result.issues:
        lines.append("Problemas:")
        for issue in review_result.issues:
            lines.append(f"- {issue.severity}: {issue.description}")
            if issue.related_test:
                lines.append(f"  Teste relacionado: {issue.related_test}")
            if issue.suggested_fix:
                lines.append(f"  Correção sugerida: {issue.suggested_fix}")
    if review_result.missing_scenarios:
        lines.append("Cenários ausentes:")
        lines.extend(f"- {scenario}" for scenario in review_result.missing_scenarios)
    if review_result.suggested_fixes:
        lines.append("Correções sugeridas:")
        lines.extend(f"- {fix}" for fix in review_result.suggested_fixes)
    return "\n".join(lines)


def _commit_and_push_test_fixes(
    repo_path: Path,
    branch_name: str,
    fixed_files: list[str],
) -> None:
    unique_files = sorted(set(fixed_files))
    if not unique_files:
        return

    run_git(["config", "user.name", "qagent[bot]"], repo_path)
    run_git(["config", "user.email", "qagent[bot]@users.noreply.github.com"], repo_path)

    for file_path in unique_files:
        run_git(["add", file_path], repo_path)

    diff_result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if diff_result.returncode == 0:
        return
    if diff_result.returncode not in {0, 1}:
        raise RuntimeError(
            "Erro git ao verificar diff staged\n"
            f"stdout: {diff_result.stdout}\n"
            f"stderr: {diff_result.stderr}"
        )

    run_git(
        [
            "commit",
            "-m",
            "test: fix generated tests from CI feedback [skip-qagent]",
        ],
        repo_path,
    )
    run_git(["push", "origin", branch_name], repo_path)


if __name__ == "__main__":
    main()
