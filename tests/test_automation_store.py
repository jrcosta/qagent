from concurrent.futures import ThreadPoolExecutor

from src.schemas.automation import AutomationEvent, RepositoryRegistration
from src.services.automation_store import AutomationStore


def _event(delivery_id: str = "delivery-1") -> AutomationEvent:
    return AutomationEvent(
        delivery_id=delivery_id,
        event_name="pull_request",
        action="synchronize",
        repository="owner/repo",
        base_sha="base",
        head_sha="head",
    )


def test_store_registers_repository_and_deduplicates_jobs(tmp_path) -> None:
    store = AutomationStore(tmp_path / "automation.db")
    registration = RepositoryRegistration(
        full_name="owner/repo",
        local_path=str(tmp_path / "repo"),
        output_root=str(tmp_path / "outputs"),
    )
    store.register_repository(registration)

    first, created_first = store.enqueue(_event())
    second, created_second = store.enqueue(_event())

    assert store.get_repository("owner/repo") == registration
    assert created_first is True
    assert created_second is False
    assert first.job_id == second.job_id


def test_store_claims_completes_and_reports_metrics(tmp_path) -> None:
    store = AutomationStore(tmp_path / "automation.db")
    store.register_repository(
        RepositoryRegistration(
            full_name="owner/repo",
            local_path=str(tmp_path / "repo"),
            output_root=str(tmp_path / "outputs"),
        )
    )
    queued, _ = store.enqueue(_event())

    running = store.claim_next("worker-1")
    assert running is not None
    assert running.job_id == queued.job_id
    assert running.status == "RUNNING"
    assert running.attempts == 1

    store.complete(
        running.job_id,
        coordinator_run_id="run-1",
        coordinator_status="ESCALATED",
    )
    completed = store.get_job(running.job_id)
    assert completed is not None
    assert completed.status == "SUCCEEDED"
    assert completed.coordinator_status == "ESCALATED"
    assert store.metrics().escalated_runs == 1


def test_store_retries_then_dead_letters(tmp_path) -> None:
    store = AutomationStore(tmp_path / "automation.db")
    job, _ = store.enqueue(_event(), max_attempts=2)

    first = store.claim_next("worker-1")
    assert first is not None
    retried = store.fail(
        job.job_id,
        "falha temporária",
        retry_delay_seconds=0,
    )
    assert retried.status == "QUEUED"

    second = store.claim_next("worker-1")
    assert second is not None
    dead = store.fail(
        job.job_id,
        "falha permanente",
        retry_delay_seconds=0,
    )
    assert dead.status == "DEAD_LETTER"


def test_store_recovers_expired_lease(tmp_path) -> None:
    store = AutomationStore(tmp_path / "automation.db")
    store.enqueue(_event())
    running = store.claim_next("worker-1", lease_seconds=-1)
    assert running is not None

    recovered = store.recover_expired_leases()
    job = store.get_job(running.job_id)

    assert recovered == 1
    assert job is not None
    assert job.status == "QUEUED"


def test_store_dead_letters_expired_lease_after_max_attempts(tmp_path) -> None:
    store = AutomationStore(tmp_path / "automation.db")
    store.enqueue(_event(), max_attempts=1)
    running = store.claim_next("worker-1", lease_seconds=-1)
    assert running is not None

    store.recover_expired_leases()
    job = store.get_job(running.job_id)

    assert job is not None
    assert job.status == "DEAD_LETTER"


def test_concurrent_workers_cannot_claim_same_job(tmp_path) -> None:
    store = AutomationStore(tmp_path / "automation.db")
    store.enqueue(_event())

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda worker_id: store.claim_next(worker_id),
                ["worker-1", "worker-2"],
            )
        )

    claimed = [job for job in results if job is not None]
    assert len(claimed) == 1
