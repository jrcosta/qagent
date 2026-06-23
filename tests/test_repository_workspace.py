import subprocess
from pathlib import Path

from src.schemas.automation import RepositoryRegistration
from src.services.repository_workspace import RepositoryWorkspaceManager


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_workspace_manager_creates_and_cleans_isolated_worktree(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "user.email", "test@example.com")
    (repo / "service.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", "service.py")
    _git(repo, "commit", "-m", "initial")
    head_sha = _git(repo, "rev-parse", "HEAD")

    manager = RepositoryWorkspaceManager(tmp_path / "workspaces")
    registration = RepositoryRegistration(
        full_name="owner/repo",
        local_path=str(repo),
        output_root=str(tmp_path / "outputs"),
        auto_fetch=False,
    )

    with manager.prepare(
        registration,
        job_id="job-1",
        head_sha=head_sha,
    ) as workspace:
        assert workspace != repo
        assert (workspace / "service.py").read_text(encoding="utf-8") == (
            "VALUE = 1\n"
        )
        (workspace / "service.py").write_text("VALUE = 2\n", encoding="utf-8")
        assert (repo / "service.py").read_text(encoding="utf-8") == "VALUE = 1\n"

    assert not (tmp_path / "workspaces" / "job-1").exists()
