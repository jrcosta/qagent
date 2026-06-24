from types import SimpleNamespace

from src.schemas.automation import RepositoryRegistration
from src.services.automation_store import AutomationStore
from src.services.repository_monitor import RepositoryMonitor


class FakeRepository:
    def get_pulls(self, **kwargs):
        return [
            SimpleNamespace(
                number=42,
                base=SimpleNamespace(sha="base"),
                head=SimpleNamespace(sha="head", ref="feature"),
            )
        ]


class FakeGithub:
    def get_repo(self, full_name):
        assert full_name == "owner/repo"
        return FakeRepository()


def test_monitor_reconciles_open_prs_idempotently(tmp_path) -> None:
    store = AutomationStore(tmp_path / "automation.db")
    store.register_repository(
        RepositoryRegistration(
            full_name="owner/repo",
            local_path=str(tmp_path / "repo"),
            output_root=str(tmp_path / "outputs"),
        )
    )
    monitor = RepositoryMonitor(
        store=store,
        github_token="",
        github_client=FakeGithub(),
    )

    first = monitor.poll_once()
    second = monitor.poll_once()
    jobs = store.list_jobs()

    assert first == 1
    assert second == 0
    assert len(jobs) == 1
    assert jobs[0].delivery_id == "poll:owner/repo:42:head"
    assert jobs[0].fetch_ref == "refs/pull/42/head"
    assert jobs[0].pr_number == 42
