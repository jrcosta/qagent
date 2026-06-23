from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


CoordinatorStatus = Literal[
    "PENDING",
    "ANALYSIS_RUNNING",
    "ANALYSIS_COMPLETED",
    "TEST_LIFECYCLE_RUNNING",
    "COMPLETED",
    "ESCALATED",
    "FAILED",
]


class CoordinatorState(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    repo_path: str
    output_dir: str
    base_sha: str | None = None
    head_sha: str | None = None
    cooperative_analysis: bool = False
    run_test_lifecycle: bool = True
    status: CoordinatorStatus = "PENDING"
    artifacts_file: str | None = None
    analysis_report_file: str | None = None
    eligible_files: int = 0
    escalated_files: int = 0
    error: str | None = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()
