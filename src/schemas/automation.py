from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


JobStatus = Literal[
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "DEAD_LETTER",
]
TriggerEvent = Literal["pull_request", "push"]


class RepositoryRegistration(BaseModel):
    full_name: str = Field(..., pattern=r"^[^/\s]+/[^/\s]+$")
    local_path: str
    output_root: str
    enabled: bool = True
    cooperative_analysis: bool = False
    auto_fetch: bool = True
    allow_test_execution: bool = False
    allowed_events: list[TriggerEvent] = Field(
        default_factory=lambda: ["pull_request"]
    )


class AutomationEvent(BaseModel):
    delivery_id: str
    event_name: TriggerEvent
    action: str
    repository: str
    base_sha: str
    head_sha: str
    ref: str | None = None
    fetch_ref: str | None = None
    received_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class AutomationJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    delivery_id: str
    repository: str
    event_name: TriggerEvent
    action: str
    base_sha: str
    head_sha: str
    ref: str | None = None
    fetch_ref: str | None = None
    status: JobStatus = "QUEUED"
    attempts: int = 0
    max_attempts: int = 3
    available_at: str
    lease_until: str | None = None
    worker_id: str | None = None
    coordinator_run_id: str | None = None
    coordinator_status: str | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class QueueMetrics(BaseModel):
    queued: int = 0
    running: int = 0
    succeeded: int = 0
    failed: int = 0
    dead_letter: int = 0
    escalated_runs: int = 0
    registered_repositories: int = 0
    active_workers: int = 0
