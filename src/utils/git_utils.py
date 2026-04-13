import subprocess
from pathlib import Path


IGNORED_EXTENSIONS = {
    ".md",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".lock",
}

IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "__pycache__",
    "outputs",
}


def get_changed_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
        shell=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Erro ao executar git diff.\n"
            f"stdout:\n{result.stdout}\n\n"
            f"stderr:\n{result.stderr}"
        )

    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return [file for file in files if should_analyze_file(file)]


def should_analyze_file(file_path: str) -> bool:
    path = Path(file_path)

    if not path.exists():
        return False

    if any(part in IGNORED_DIRECTORIES for part in path.parts):
        return False

    if path.suffix.lower() in IGNORED_EXTENSIONS:
        return False

    return path.is_file()