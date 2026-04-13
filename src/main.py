from pathlib import Path

from src.config.settings import get_settings
from src.crew.qa_crew import QACrewRunner
from src.utils.git_utils import get_changed_files


def read_file_content(file_path: str) -> str:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    return path.read_text(encoding="utf-8")


def save_output(content: str) -> None:
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "analysis.md"
    output_file.write_text(content, encoding="utf-8")


def build_report(sections: list[str]) -> str:
    return "\n\n---\n\n".join(sections)


def main() -> None:
    settings = get_settings()
    crew_runner = QACrewRunner(settings)

    changed_files = get_changed_files()

    if not changed_files:
        message = "# Nenhum arquivo alterado relevante encontrado para análise."
        save_output(message)
        print(message)
        return

    analyses = []

    for file_path in changed_files:
        print(f"Analisando: {file_path}")
        code_content = read_file_content(file_path)

        result = crew_runner.run(
            file_path=file_path,
            code_content=code_content,
        )

        section = f"# Arquivo analisado: {file_path}\n\n{result}"
        analyses.append(section)

    final_report = build_report(analyses)
    save_output(final_report)

    print("\nAnálise salva em:")
    print("outputs/analysis.md")


if __name__ == "__main__":
    main()