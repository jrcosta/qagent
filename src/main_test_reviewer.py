import json
import os
import sys
import time
from argparse import ArgumentParser
from pathlib import Path

from src.config.settings import get_settings
from src.crew.test_reviewer_crew import TestReviewerCrewRunner
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.schemas.test_strategy_result import render_test_strategy_result_for_prompt
from src.utils.git_utils import get_file_diff
from src.utils.pr_utils import add_pr_comment, get_repo_full_name, get_current_branch
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
    
    all_findings = []

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
        )
        artifact.generated_test_review_result = review_result
        artifact.record_duration("test_review", (time.perf_counter() - t0) * 1000)
        artifact.mark_step_executed("test_review")

        print(f"  📝 Status da Revisão: {review_result.status}")
        if review_result.issues:
            print(f"  ⚠️ {len(review_result.issues)} problema(s) identificado(s).")

        finding = review_result_to_finding(artifact.file_path, review_result)
        if finding:
            all_findings.append(finding)

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

    repo_full_name = get_repo_full_name(repo_path)
    
    # Tenta obter o nome da branch do arquivo salvo pelo generator
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


if __name__ == "__main__":
    main()
