from __future__ import annotations

import threading
import time
from pathlib import Path
from uuid import uuid4

from src.config.settings import Settings
from src.schemas.automation import AutomationJob
from src.services.agentic_coordinator import AgenticRepositoryCoordinator
from src.services.automation_store import AutomationStore
from src.services.coordinator_state_store import JsonCoordinatorStateStore
from src.services.repository_workspace import RepositoryWorkspaceManager


class AutomationWorker:
    def __init__(
        self,
        *,
        settings: Settings,
        store: AutomationStore,
        workspace_manager: RepositoryWorkspaceManager,
        worker_id: str | None = None,
        lease_seconds: int = 900,
        coordinator_factory=None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.workspace_manager = workspace_manager
        self.worker_id = worker_id or f"worker-{uuid4()}"
        self.lease_seconds = lease_seconds
        self.coordinator_factory = (
            coordinator_factory or self._create_coordinator
        )

    def run_once(self) -> AutomationJob | None:
        self.store.touch_worker(self.worker_id)
        self.store.recover_expired_leases()
        job = self.store.claim_next(
            self.worker_id,
            lease_seconds=self.lease_seconds,
        )
        if job is None:
            return None
        self.store.touch_worker(self.worker_id, job.job_id)

        registration = self.store.get_repository(job.repository)
        if registration is None or not registration.enabled:
            self.store.dead_letter(
                job.job_id,
                f"Repositório não registrado ou desabilitado: {job.repository}",
            )
            self.store.touch_worker(self.worker_id)
            return self.store.get_job(job.job_id)
        if job.event_name not in registration.allowed_events:
            self.store.dead_letter(
                job.job_id,
                f"Evento não autorizado para o repositório: {job.event_name}",
            )
            self.store.touch_worker(self.worker_id)
            return self.store.get_job(job.job_id)

        stop_heartbeat = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat_loop,
            args=(job.job_id, stop_heartbeat),
            daemon=True,
        )
        heartbeat.start()
        try:
            with self.workspace_manager.prepare(
                registration,
                job_id=job.job_id,
                head_sha=job.head_sha,
                fetch_ref=job.fetch_ref,
            ) as workspace:
                output_dir = (
                    Path(registration.output_root).resolve()
                    / _safe_repo_name(job.repository)
                    / job.job_id
                )
                coordinator = self.coordinator_factory(output_dir)
                if job.coordinator_run_id:
                    state = coordinator.resume(
                        job.coordinator_run_id,
                        repo_path=workspace,
                    )
                else:
                    self.store.attach_coordinator_run(
                        job.job_id,
                        job.job_id,
                    )
                    state = coordinator.run(
                        repo_path=workspace,
                        output_dir=output_dir,
                        base_sha=job.base_sha,
                        head_sha=job.head_sha,
                        cooperative_analysis=registration.cooperative_analysis,
                        run_id=job.job_id,
                        run_test_lifecycle=registration.allow_test_execution,
                    )
                if state.status == "FAILED":
                    raise RuntimeError(state.error or "Coordinator falhou")
                self.store.complete(
                    job.job_id,
                    coordinator_run_id=state.run_id,
                    coordinator_status=state.status,
                )
        except Exception as exc:
            self.store.fail(job.job_id, str(exc))
        finally:
            stop_heartbeat.set()
            heartbeat.join(timeout=2)
            self.store.touch_worker(self.worker_id)
        return self.store.get_job(job.job_id)

    def run_forever(
        self,
        *,
        poll_interval_seconds: float = 2.0,
        stop_event: threading.Event | None = None,
    ) -> None:
        stop = stop_event or threading.Event()
        while not stop.is_set():
            self.store.touch_worker(self.worker_id)
            job = self.run_once()
            if job is None:
                stop.wait(poll_interval_seconds)

    def _heartbeat_loop(
        self,
        job_id: str,
        stop: threading.Event,
    ) -> None:
        interval = max(self.lease_seconds / 3, 1)
        while not stop.wait(interval):
            self.store.touch_worker(self.worker_id, job_id)
            if not self.store.heartbeat(
                job_id,
                self.worker_id,
                lease_seconds=self.lease_seconds,
            ):
                return

    def _create_coordinator(
        self,
        output_dir: Path,
    ) -> AgenticRepositoryCoordinator:
        return AgenticRepositoryCoordinator(
            self.settings,
            state_store=JsonCoordinatorStateStore(
                output_dir / "coordinator_runs"
            ),
        )


def _safe_repo_name(full_name: str) -> str:
    return full_name.replace("/", "__")
