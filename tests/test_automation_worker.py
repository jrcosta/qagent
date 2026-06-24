from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from src.config.settings import Settings
from src.schemas.automation import AutomationEvent, RepositoryRegistration
from src.services.automation_store import AutomationStore
from src.services.automation_worker import AutomationWorker


class FakeWorkspaceManager:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.calls = 0

    @contextmanager
    def prepare(self, registration, *, job_id, head_sha, fetch_ref=None):
        self.calls += 1
        self.workspace.mkdir(parents=True, exist_ok=True)
        yield self.workspace


class FakeCoordinator:
    def __init__(self, status: str = "COMPLETED") -> None:
        self.status = status
        self.calls = 0
        self.last_kwargs = {}
        self.last_resume_repo_path = None

    def run(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        return SimpleNamespace(
            run_id=kwargs.get("run_id", "coordinator-1"),
            status=self.status,
            error=None,
            artifacts_file=None,
            analysis_report_file=None,
            eligible_files=0,
            escalated_files=1 if self.status == "ESCALATED" else 0,
        )

    def resume(self, run_id, repo_path=None):
        self.calls += 1
        self.last_resume_repo_path = repo_path
        return SimpleNamespace(
            run_id=run_id,
            status=self.status,
            error=None,
            artifacts_file=None,
            analysis_report_file=None,
            eligible_files=0,
            escalated_files=0,
        )


class FakeFeedbackPublisher:
    def __init__(
        self,
        comment_url: str | None = "https://github.com/owner/repo/pull/1#comment",
    ) -> None:
        self.comment_url = comment_url
        self.calls = []

    def publish(self, *, job, state):
        self.calls.append((job, state))
        return self.comment_url


def test_worker_processes_registered_repository(tmp_path) -> None:
    store = AutomationStore(tmp_path / "automation.db")
    store.register_repository(
        RepositoryRegistration(
            full_name="owner/repo",
            local_path=str(tmp_path / "repo"),
            output_root=str(tmp_path / "outputs"),
            auto_fetch=False,
            allow_test_execution=True,
        )
    )
    job, _ = store.enqueue(
        AutomationEvent(
            delivery_id="delivery-1",
            event_name="pull_request",
            action="synchronize",
            repository="owner/repo",
            base_sha="base",
            head_sha="head",
            pr_number=42,
        )
    )
    workspace = FakeWorkspaceManager(tmp_path / "workspace")
    coordinator = FakeCoordinator(status="ESCALATED")
    worker = AutomationWorker(
        settings=Settings(),
        store=store,
        workspace_manager=workspace,  # type: ignore[arg-type]
        worker_id="worker-1",
        lease_seconds=30,
        coordinator_factory=lambda output: coordinator,
    )

    result = worker.run_once()

    assert result is not None
    assert result.job_id == job.job_id
    assert result.status == "SUCCEEDED"
    assert result.coordinator_status == "ESCALATED"
    assert result.coordinator_run_id == job.job_id
    assert result.feedback_status == "SKIPPED"
    assert workspace.calls == 1
    assert coordinator.calls == 1
    assert store.metrics().active_workers == 1


def test_worker_dead_letters_unregistered_repository(tmp_path) -> None:
    store = AutomationStore(tmp_path / "automation.db")
    store.enqueue(
        AutomationEvent(
            delivery_id="delivery-1",
            event_name="pull_request",
            action="opened",
            repository="owner/missing",
            base_sha="base",
            head_sha="head",
        )
    )
    worker = AutomationWorker(
        settings=Settings(),
        store=store,
        workspace_manager=FakeWorkspaceManager(tmp_path / "workspace"),  # type: ignore[arg-type]
        worker_id="worker-1",
    )

    result = worker.run_once()

    assert result is not None
    assert result.status == "DEAD_LETTER"


def test_worker_disables_test_execution_by_default(tmp_path) -> None:
    store = AutomationStore(tmp_path / "automation.db")
    store.register_repository(
        RepositoryRegistration(
            full_name="owner/repo",
            local_path=str(tmp_path / "repo"),
            output_root=str(tmp_path / "outputs"),
            auto_fetch=False,
        )
    )
    store.enqueue(
        AutomationEvent(
            delivery_id="delivery-analysis-only",
            event_name="pull_request",
            action="opened",
            repository="owner/repo",
            base_sha="base",
            head_sha="head",
        )
    )
    coordinator = FakeCoordinator()
    worker = AutomationWorker(
        settings=Settings(),
        store=store,
        workspace_manager=FakeWorkspaceManager(tmp_path / "workspace"),  # type: ignore[arg-type]
        coordinator_factory=lambda output: coordinator,
    )

    result = worker.run_once()

    assert result is not None
    assert result.status == "SUCCEEDED"
    assert coordinator.last_kwargs["run_test_lifecycle"] is False


def test_worker_resumes_existing_coordinator_run(tmp_path) -> None:
    store = AutomationStore(tmp_path / "automation.db")
    store.register_repository(
        RepositoryRegistration(
            full_name="owner/repo",
            local_path=str(tmp_path / "repo"),
            output_root=str(tmp_path / "outputs"),
            auto_fetch=False,
            allow_test_execution=True,
        )
    )
    job, _ = store.enqueue(
        AutomationEvent(
            delivery_id="delivery-resume",
            event_name="pull_request",
            action="synchronize",
            repository="owner/repo",
            base_sha="base",
            head_sha="head",
        )
    )
    store.attach_coordinator_run(job.job_id, "existing-run")
    coordinator = FakeCoordinator()
    worker = AutomationWorker(
        settings=Settings(),
        store=store,
        workspace_manager=FakeWorkspaceManager(tmp_path / "workspace"),  # type: ignore[arg-type]
        worker_id="worker-1",
        coordinator_factory=lambda output: coordinator,
    )

    result = worker.run_once()

    assert result is not None
    assert result.status == "SUCCEEDED"
    assert result.coordinator_run_id == "existing-run"
    assert coordinator.calls == 1
    assert coordinator.last_resume_repo_path == (tmp_path / "workspace")


def test_worker_publishes_pr_feedback_when_available(tmp_path) -> None:
    store = AutomationStore(tmp_path / "automation.db")
    store.register_repository(
        RepositoryRegistration(
            full_name="owner/repo",
            local_path=str(tmp_path / "repo"),
            output_root=str(tmp_path / "outputs"),
            auto_fetch=False,
        )
    )
    store.enqueue(
        AutomationEvent(
            delivery_id="delivery-feedback",
            event_name="pull_request",
            action="synchronize",
            repository="owner/repo",
            base_sha="base",
            head_sha="head",
            pr_number=42,
        )
    )
    publisher = FakeFeedbackPublisher()
    worker = AutomationWorker(
        settings=Settings(github_token="token"),
        store=store,
        workspace_manager=FakeWorkspaceManager(tmp_path / "workspace"),  # type: ignore[arg-type]
        coordinator_factory=lambda output: FakeCoordinator(),
        feedback_publisher=publisher,
    )

    result = worker.run_once()

    assert result is not None
    assert result.status == "SUCCEEDED"
    assert result.feedback_status == "PUBLISHED"
    assert result.feedback_comment_url == publisher.comment_url
    assert len(publisher.calls) == 1
