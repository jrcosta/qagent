from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


CapabilityName = Literal[
    "evaluate_risk",
    "build_test_strategy",
    "enrich_high_risk",
    "evaluate_final",
    "generate_tests",
    "write_tests",
    "execute_tests",
    "review_tests",
    "fix_tests",
]
PlanPhase = Literal["analysis", "test_lifecycle"]
PlannerSource = Literal["llm", "deterministic_fallback"]
RunStatus = Literal["PENDING", "RUNNING", "COMPLETED", "ESCALATED", "FAILED"]
StepStatus = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED"]
EvaluationAction = Literal["CONTINUE", "COMPLETE", "RETRY", "CORRECT", "ESCALATE"]


class CapabilityDefinition(BaseModel):
    name: CapabilityName
    description: str
    requires: list[CapabilityName] = Field(default_factory=list)
    mutates_artifact: bool = True


class PlanStep(BaseModel):
    id: str = Field(..., min_length=1)
    capability: CapabilityName
    reason: str = Field(..., min_length=1)
    depends_on: list[str] = Field(default_factory=list)
    max_attempts: int = Field(default=1, ge=1, le=3)


class ExecutionPlan(BaseModel):
    objective: str = Field(..., min_length=1)
    steps: list[PlanStep] = Field(..., min_length=1, max_length=10)
    rationale: str = Field(..., min_length=1)
    planner_source: PlannerSource = "llm"
    phase: PlanPhase = "analysis"

    @model_validator(mode="after")
    def validate_graph(self) -> "ExecutionPlan":
        known_ids: set[str] = set()
        for step in self.steps:
            if step.id in known_ids:
                raise ValueError(f"step id duplicado: {step.id}")
            unknown_dependencies = set(step.depends_on) - known_ids
            if unknown_dependencies:
                raise ValueError(
                    f"step '{step.id}' depende de steps futuros/desconhecidos: "
                    f"{sorted(unknown_dependencies)}"
                )
            known_ids.add(step.id)
        return self


class StepExecutionRecord(BaseModel):
    step_id: str
    capability: CapabilityName
    status: StepStatus = "PENDING"
    attempts: int = 0
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None


class EvaluationDecision(BaseModel):
    action: EvaluationAction
    reason: str
    target_step_id: str | None = None
    correction_capabilities: list[CapabilityName] = Field(default_factory=list)


class RunState(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    file_path: str
    plan: ExecutionPlan
    status: RunStatus = "PENDING"
    current_step_id: str | None = None
    steps: list[StepExecutionRecord] = Field(default_factory=list)
    decisions: list[EvaluationDecision] = Field(default_factory=list)
    artifact_snapshot: dict[str, Any] = Field(default_factory=dict)
    correction_cycles: int = 0
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()
