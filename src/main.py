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

    settings = get_settings()
    crew_runner = QACrewRunner(settings)

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
        )

        section = f"# Arquivo analisado: {file_path}\n\n{result}"
        analyses.append(section)

    if not analyses:
        message = "# Nenhum diff relevante encontrado para análise."
        save_output(message, args.output_file)
        print(message)
        return

    final_report = build_report(analyses)
    save_output(final_report, args.output_file)

    print("\nAnálise salva em:")
    print(args.output_file)


if __name__ == "__main__":
    main()