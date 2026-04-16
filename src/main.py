from argparse import ArgumentParser
from pathlib import Path

from src.config.settings import get_settings
from src.crew.qa_crew import QACrewRunner
from src.utils.git_utils import get_changed_files, get_file_diff


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

    parser.add_argument(
        "--repo-owner",
        default="unknown-owner",
        help="Owner do repositório analisado",
    )

    parser.add_argument(
        "--repo-name",
        default=None,
        help="Nome do repositório analisado. Se omitido, usa o nome da pasta do repo.",
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


def build_report(sections: list[str], repo_owner: str, repo_name: str, base_sha: str | None, head_sha: str | None) -> str:
    header = (
        f"# QAgent Report\n\n"
        f"- **Repositório:** {repo_owner}/{repo_name}\n"
        f"- **Base SHA:** {base_sha or '-'}\n"
        f"- **Head SHA:** {head_sha or '-'}\n"
    )
    body = "\n\n---\n\n".join(sections)
    return f"{header}\n\n---\n\n{body}"


def main() -> None:
    args = parse_args()
    repo_path = Path(args.repo_path).resolve()
    repo_name = args.repo_name or repo_path.name

    settings = get_settings()
    crew_runner = QACrewRunner(settings)

    changed_files = get_changed_files(
        repo_path=repo_path,
        base_sha=args.base_sha,
        head_sha=args.head_sha,
    )

    if not changed_files:
        message = (
            "# Nenhum arquivo alterado relevante encontrado para análise.\n\n"
            f"- **Repositório:** {args.repo_owner}/{repo_name}\n"
            f"- **Base SHA:** {args.base_sha or '-'}\n"
            f"- **Head SHA:** {args.head_sha or '-'}\n"
        )
        save_output(message, args.output_file)
        print(message)
        return

    analyses = []

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

        result = crew_runner.run(
            file_path=file_path,
            file_diff=file_diff,
            code_content=code_content,
            repo_path=str(repo_path),
        )

        section = f"# Arquivo analisado: {file_path}\n\n{result}"
        analyses.append(section)

    if not analyses:
        message = (
            "# Nenhum diff relevante encontrado para análise.\n\n"
            f"- **Repositório:** {args.repo_owner}/{repo_name}\n"
            f"- **Base SHA:** {args.base_sha or '-'}\n"
            f"- **Head SHA:** {args.head_sha or '-'}\n"
        )
        save_output(message, args.output_file)
        print(message)
        return

    final_report = build_report(
        sections=analyses,
        repo_owner=args.repo_owner,
        repo_name=repo_name,
        base_sha=args.base_sha,
        head_sha=args.head_sha,
    )
    save_output(final_report, args.output_file)

    print("\nAnálise salva em:")
    print(args.output_file)


if __name__ == "__main__":
    main()
