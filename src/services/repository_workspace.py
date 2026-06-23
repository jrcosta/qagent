from __future__ import annotations

import subprocess
import shutil
from contextlib import contextmanager
from pathlib import Path

from src.schemas.automation import RepositoryRegistration


class RepositoryWorkspaceManager:
    """Cria worktrees isolados sem modificar o checkout registrado."""

    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def prepare(
        self,
        registration: RepositoryRegistration,
        *,
        job_id: str,
        head_sha: str,
        fetch_ref: str | None = None,
    ):
        repository = Path(registration.local_path).resolve()
        if not (repository / ".git").exists():
            raise ValueError(
                f"Repositório registrado não é um checkout Git: {repository}"
            )

        workspace = (self.workspace_root / job_id).resolve()
        if not workspace.is_relative_to(self.workspace_root):
            raise ValueError("Workspace resolve fora da raiz autorizada")
        if workspace.exists():
            self._remove_worktree(repository, workspace)

        if registration.auto_fetch:
            if fetch_ref:
                _run_git(repository, ["fetch", "origin", fetch_ref])
            else:
                _run_git(repository, ["fetch", "--all", "--prune"])
        _run_git(
            repository,
            ["worktree", "add", "--detach", str(workspace), head_sha],
        )
        try:
            yield workspace
        finally:
            self._remove_worktree(repository, workspace)

    def _remove_worktree(self, repository: Path, workspace: Path) -> None:
        if not workspace.exists():
            return
        resolved = workspace.resolve()
        if not resolved.is_relative_to(self.workspace_root):
            raise ValueError("Recusa ao remover workspace fora da raiz autorizada")
        _run_git(
            repository,
            ["worktree", "remove", "--force", str(resolved)],
            check=False,
        )
        if resolved.exists():
            shutil.rmtree(resolved)


def validate_repository_registration(
    registration: RepositoryRegistration,
) -> RepositoryRegistration:
    repository = Path(registration.local_path).resolve()
    if not repository.is_dir():
        raise ValueError(f"local_path não existe ou não é diretório: {repository}")
    if not (repository / ".git").exists():
        raise ValueError(f"local_path não é checkout Git: {repository}")
    output_root = Path(registration.output_root).resolve()
    if (
        output_root == repository
        or repository.is_relative_to(output_root)
        or output_root.is_relative_to(repository)
    ):
        raise ValueError(
            "output_root não pode sobrepor o caminho do repositório"
        )
    output_root.mkdir(parents=True, exist_ok=True)
    registration.local_path = str(repository)
    registration.output_root = str(output_root)
    return registration


def _run_git(
    repository: Path,
    arguments: list[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(arguments)} falhou em {repository}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result
