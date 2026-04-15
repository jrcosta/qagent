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


def run_git_command(command: list[str], repo_path: Path) -> subprocess.CompletedProcess:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=repo_path,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Erro ao executar comando git.\n"
            f"Comando: {' '.join(command)}\n"
            f"Repo: {repo_path}\n"
            f"stdout:\n{result.stdout}\n\n"
            f"stderr:\n{result.stderr}"
        )

    return result


def get_changed_files(
    repo_path: Path,
    base_sha: str | None = None,
    head_sha: str | None = None,
) -> list[str]:
    if base_sha and head_sha:
        result = run_git_command(
            ["git", "diff", "--name-only", base_sha, head_sha],
            repo_path,
        )
        files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    else:
        result = run_git_command(["git", "status", "--porcelain"], repo_path)
        files = parse_git_status_output(result.stdout)

    return [file for file in files if should_analyze_file(file, repo_path)]


def get_file_diff(
    file_path: str,
    repo_path: Path,
    base_sha: str | None = None,
    head_sha: str | None = None,
) -> str:
    if base_sha and head_sha:
        result = run_git_command(
            ["git", "diff", base_sha, head_sha, "--", file_path],
            repo_path,
        )
    else:
        result = run_git_command(
            ["git", "diff", "--", file_path],
            repo_path,
        )

    return result.stdout.strip()


def parse_git_status_output(output: str) -> list[str]:
    files = []

    for line in output.splitlines():
        if not line.strip():
            continue

        if len(line) > 3:
            file_path = line[3:].strip()
            files.append(file_path)

    return files


def should_analyze_file(file_path: str, repo_path: Path) -> bool:
    path = repo_path / file_path

    if not path.exists():
        return False

    if any(part in IGNORED_DIRECTORIES for part in path.parts):
        return False

    if path.suffix.lower() in IGNORED_EXTENSIONS:
        return False

    return path.is_file()