from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.schemas.automation import (
    AutomationEvent,
    AutomationJob,
    QueueMetrics,
    RepositoryRegistration,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


class AutomationStore:
    """Registro de repositórios e fila persistente usando SQLite."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(
            self.database_path,
            timeout=30,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS repositories (
                    full_name TEXT PRIMARY KEY,
                    config_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    delivery_id TEXT NOT NULL UNIQUE,
                    repository TEXT NOT NULL,
                    event_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    base_sha TEXT NOT NULL,
                    head_sha TEXT NOT NULL,
                    ref TEXT,
                    fetch_ref TEXT,
                    pr_number INTEGER,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    max_attempts INTEGER NOT NULL,
                    available_at TEXT NOT NULL,
                    lease_until TEXT,
                    worker_id TEXT,
                    coordinator_run_id TEXT,
                    coordinator_status TEXT,
                    feedback_status TEXT NOT NULL DEFAULT 'PENDING',
                    feedback_error TEXT,
                    feedback_comment_url TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS jobs_claim_idx
                ON jobs(status, available_at, created_at);

                CREATE TABLE IF NOT EXISTS workers (
                    worker_id TEXT PRIMARY KEY,
                    last_seen_at TEXT NOT NULL,
                    current_job_id TEXT
                );
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
            }
            if "coordinator_status" not in columns:
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN coordinator_status TEXT"
                )
            if "fetch_ref" not in columns:
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN fetch_ref TEXT"
                )
            if "pr_number" not in columns:
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN pr_number INTEGER"
                )
            if "feedback_status" not in columns:
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN feedback_status TEXT NOT NULL DEFAULT 'PENDING'"
                )
            if "feedback_error" not in columns:
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN feedback_error TEXT"
                )
            if "feedback_comment_url" not in columns:
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN feedback_comment_url TEXT"
                )

    def register_repository(
        self,
        registration: RepositoryRegistration,
    ) -> None:
        now = _iso(_now())
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO repositories(full_name, config_json, enabled, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(full_name) DO UPDATE SET
                    config_json=excluded.config_json,
                    enabled=excluded.enabled,
                    updated_at=excluded.updated_at
                """,
                (
                    registration.full_name,
                    registration.model_dump_json(),
                    int(registration.enabled),
                    now,
                ),
            )

    def get_repository(
        self,
        full_name: str,
    ) -> RepositoryRegistration | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT config_json FROM repositories WHERE full_name=?",
                (full_name,),
            ).fetchone()
        if row is None:
            return None
        return RepositoryRegistration.model_validate_json(row["config_json"])

    def list_repositories(self) -> list[RepositoryRegistration]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT config_json FROM repositories ORDER BY full_name"
            ).fetchall()
        return [
            RepositoryRegistration.model_validate_json(row["config_json"])
            for row in rows
        ]

    def enqueue(
        self,
        event: AutomationEvent,
        *,
        max_attempts: int = 3,
    ) -> tuple[AutomationJob, bool]:
        now = _iso(_now())
        job = AutomationJob(
            delivery_id=event.delivery_id,
            repository=event.repository,
            event_name=event.event_name,
            action=event.action,
            base_sha=event.base_sha,
            head_sha=event.head_sha,
            ref=event.ref,
            fetch_ref=event.fetch_ref,
            pr_number=event.pr_number,
            max_attempts=max_attempts,
            available_at=now,
            created_at=now,
            updated_at=now,
        )
        with self._connection() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO jobs(
                        job_id, delivery_id, repository, event_name, action,
                        base_sha, head_sha, ref, fetch_ref, pr_number,
                        status, attempts, max_attempts,
                        available_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job.job_id,
                        job.delivery_id,
                        job.repository,
                        job.event_name,
                        job.action,
                        job.base_sha,
                        job.head_sha,
                        job.ref,
                        event.fetch_ref,
                        job.pr_number,
                        job.status,
                        job.attempts,
                        job.max_attempts,
                        job.available_at,
                        job.created_at,
                        job.updated_at,
                    ),
                )
                return job, True
            except sqlite3.IntegrityError:
                existing = self.get_job_by_delivery(event.delivery_id)
                if existing is None:
                    raise
                return existing, False

    def claim_next(
        self,
        worker_id: str,
        *,
        lease_seconds: int = 900,
    ) -> AutomationJob | None:
        now = _now()
        lease_until = now + timedelta(seconds=lease_seconds)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM jobs
                WHERE status='QUEUED' AND available_at <= ?
                ORDER BY created_at
                LIMIT 1
                """,
                (_iso(now),),
            ).fetchone()
            if row is None:
                connection.execute("COMMIT")
                return None
            connection.execute(
                """
                UPDATE jobs SET
                    status='RUNNING',
                    attempts=attempts + 1,
                    worker_id=?,
                    lease_until=?,
                    updated_at=?
                WHERE job_id=?
                """,
                (
                    worker_id,
                    _iso(lease_until),
                    _iso(now),
                    row["job_id"],
                ),
            )
            connection.execute("COMMIT")
        return self.get_job(row["job_id"])

    def touch_worker(
        self,
        worker_id: str,
        current_job_id: str | None = None,
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO workers(worker_id, last_seen_at, current_job_id)
                VALUES (?, ?, ?)
                ON CONFLICT(worker_id) DO UPDATE SET
                    last_seen_at=excluded.last_seen_at,
                    current_job_id=excluded.current_job_id
                """,
                (worker_id, _iso(_now()), current_job_id),
            )

    def heartbeat(
        self,
        job_id: str,
        worker_id: str,
        *,
        lease_seconds: int = 900,
    ) -> bool:
        now = _now()
        with self._connection() as connection:
            result = connection.execute(
                """
                UPDATE jobs SET lease_until=?, updated_at=?
                WHERE job_id=? AND worker_id=? AND status='RUNNING'
                """,
                (
                    _iso(now + timedelta(seconds=lease_seconds)),
                    _iso(now),
                    job_id,
                    worker_id,
                ),
            )
        return result.rowcount == 1

    def complete(
        self,
        job_id: str,
        *,
        coordinator_run_id: str | None = None,
        coordinator_status: str | None = None,
    ) -> None:
        self._set_terminal(
            job_id,
            "SUCCEEDED",
            coordinator_run_id=coordinator_run_id,
            coordinator_status=coordinator_status,
        )

    def mark_feedback(
        self,
        job_id: str,
        *,
        status: str,
        comment_url: str | None = None,
        error: str | None = None,
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE jobs SET
                    feedback_status=?,
                    feedback_comment_url=?,
                    feedback_error=?,
                    updated_at=?
                WHERE job_id=?
                """,
                (
                    status,
                    comment_url,
                    error[:4000] if error else None,
                    _iso(_now()),
                    job_id,
                ),
            )

    def attach_coordinator_run(
        self,
        job_id: str,
        coordinator_run_id: str,
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE jobs SET coordinator_run_id=?, updated_at=?
                WHERE job_id=?
                """,
                (coordinator_run_id, _iso(_now()), job_id),
            )

    def dead_letter(self, job_id: str, error: str) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE jobs SET
                    status='DEAD_LETTER', error=?, lease_until=NULL,
                    worker_id=NULL, updated_at=?
                WHERE job_id=?
                """,
                (error[:4000], _iso(_now()), job_id),
            )

    def fail(
        self,
        job_id: str,
        error: str,
        *,
        retry_delay_seconds: int = 60,
    ) -> AutomationJob:
        job = self.get_job(job_id)
        if job is None:
            raise FileNotFoundError(f"Job não encontrado: {job_id}")
        now = _now()
        if job.attempts >= job.max_attempts:
            status = "DEAD_LETTER"
            available_at = job.available_at
        else:
            status = "QUEUED"
            delay = retry_delay_seconds * (2 ** max(job.attempts - 1, 0))
            available_at = _iso(now + timedelta(seconds=delay))
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE jobs SET
                    status=?, error=?, available_at=?, lease_until=NULL,
                    worker_id=NULL, updated_at=?
                WHERE job_id=?
                """,
                (status, error[:4000], available_at, _iso(now), job_id),
            )
        updated = self.get_job(job_id)
        assert updated is not None
        return updated

    def recover_expired_leases(self) -> int:
        now = _iso(_now())
        with self._connection() as connection:
            dead = connection.execute(
                """
                UPDATE jobs SET
                    status='DEAD_LETTER',
                    lease_until=NULL,
                    worker_id=NULL,
                    error='Lease expirada após esgotar tentativas.',
                    updated_at=?
                WHERE status='RUNNING' AND lease_until < ?
                  AND attempts >= max_attempts
                """,
                (now, now),
            )
            queued = connection.execute(
                """
                UPDATE jobs SET
                    status='QUEUED',
                    available_at=?,
                    lease_until=NULL,
                    worker_id=NULL,
                    error='Lease expirada; job recuperado automaticamente.',
                    updated_at=?
                WHERE status='RUNNING' AND lease_until < ?
                  AND attempts < max_attempts
                """,
                (now, now, now),
            )
        return dead.rowcount + queued.rowcount

    def requeue(self, job_id: str) -> AutomationJob:
        job = self.get_job(job_id)
        if job is None:
            raise FileNotFoundError(f"Job não encontrado: {job_id}")
        if job.status not in {"DEAD_LETTER", "FAILED"}:
            raise ValueError(
                "Somente jobs FAILED ou DEAD_LETTER podem ser reencaminhados"
            )
        now = _iso(_now())
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE jobs SET
                    status='QUEUED', attempts=0, available_at=?,
                    lease_until=NULL, worker_id=NULL, error=NULL,
                    feedback_status='PENDING',
                    feedback_error=NULL,
                    feedback_comment_url=NULL,
                    updated_at=?
                WHERE job_id=?
                """,
                (now, now, job_id),
            )
        updated = self.get_job(job_id)
        assert updated is not None
        return updated

    def list_jobs(self, limit: int = 100) -> list[AutomationJob]:
        safe_limit = max(1, min(limit, 500))
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [_row_to_job(row) for row in rows]

    def get_job(self, job_id: str) -> AutomationJob | None:
        return self._get_job("job_id", job_id)

    def get_job_by_delivery(
        self,
        delivery_id: str,
    ) -> AutomationJob | None:
        return self._get_job("delivery_id", delivery_id)

    def metrics(self, active_worker_seconds: int = 60) -> QueueMetrics:
        with self._connection() as connection:
            counts = {
                row["status"]: row["count"]
                for row in connection.execute(
                    "SELECT status, COUNT(*) AS count FROM jobs GROUP BY status"
                ).fetchall()
            }
            repositories = connection.execute(
                "SELECT COUNT(*) AS count FROM repositories WHERE enabled=1"
            ).fetchone()["count"]
            escalated = connection.execute(
                """
                SELECT COUNT(*) AS count FROM jobs
                WHERE coordinator_status='ESCALATED'
                """
            ).fetchone()["count"]
            active_since = _iso(
                _now() - timedelta(seconds=active_worker_seconds)
            )
            active_workers = connection.execute(
                """
                SELECT COUNT(*) AS count FROM workers
                WHERE last_seen_at >= ?
                """,
                (active_since,),
            ).fetchone()["count"]
        return QueueMetrics(
            queued=counts.get("QUEUED", 0),
            running=counts.get("RUNNING", 0),
            succeeded=counts.get("SUCCEEDED", 0),
            failed=counts.get("FAILED", 0),
            dead_letter=counts.get("DEAD_LETTER", 0),
            escalated_runs=escalated,
            registered_repositories=repositories,
            active_workers=active_workers,
        )

    def _get_job(self, field: str, value: str) -> AutomationJob | None:
        if field not in {"job_id", "delivery_id"}:
            raise ValueError("Campo de consulta inválido")
        with self._connection() as connection:
            row = connection.execute(
                f"SELECT * FROM jobs WHERE {field}=?",
                (value,),
            ).fetchone()
        return _row_to_job(row) if row else None

    def _set_terminal(
        self,
        job_id: str,
        status: str,
        *,
        coordinator_run_id: str | None = None,
        coordinator_status: str | None = None,
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE jobs SET
                    status=?, coordinator_run_id=?, coordinator_status=?,
                    lease_until=NULL,
                    worker_id=NULL, error=NULL, updated_at=?
                WHERE job_id=?
                """,
                (
                    status,
                    coordinator_run_id,
                    coordinator_status,
                    _iso(_now()),
                    job_id,
                ),
            )


def _row_to_job(row: sqlite3.Row) -> AutomationJob:
    return AutomationJob(**dict(row))
