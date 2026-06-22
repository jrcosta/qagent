from __future__ import annotations

from datetime import datetime, timezone

from src.schemas.agentic_runtime import (
    CapabilityName,
    EvaluationDecision,
    ExecutionPlan,
    PlanStep,
    RunState,
    StepExecutionRecord,
)
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.services.agentic_evaluator import AgenticRunEvaluator
from src.services.analysis_orchestrator import AnalysisOrchestrator
from src.services.run_state_store import JsonRunStateStore
from src.services.capability_catalog import validate_execution_plan


class GovernedAgenticRuntime:
    """Executor de planos tipados com persistência e decisões governadas."""

    MAX_CORRECTION_CYCLES = 1

    def __init__(
        self,
        orchestrator: AnalysisOrchestrator,
        state_store: JsonRunStateStore,
        evaluator: AgenticRunEvaluator | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.state_store = state_store
        self.evaluator = evaluator or AgenticRunEvaluator()

    def run(
        self,
        artifact: FileAnalysisArtifact,
        plan: ExecutionPlan,
    ) -> RunState:
        validate_execution_plan(plan)
        state = RunState(
            file_path=artifact.file_path,
            plan=plan,
            steps=[
                StepExecutionRecord(
                    step_id=step.id,
                    capability=step.capability,
                )
                for step in plan.steps
            ],
        )
        artifact.agentic_run_id = state.run_id
        artifact.execution_plan = plan
        state.artifact_snapshot = artifact.model_dump(mode="json")
        state.status = "RUNNING"
        self.state_store.save(state)
        return self._execute(artifact, state)

    def resume(
        self,
        artifact: FileAnalysisArtifact,
        run_id: str,
    ) -> RunState:
        """Retoma uma execução persistida sem repetir passos concluídos."""
        state = self.state_store.load(run_id)
        if state.file_path != artifact.file_path:
            raise ValueError(
                f"RunState pertence a '{state.file_path}', não a '{artifact.file_path}'"
            )
        if state.status in {"COMPLETED", "ESCALATED", "FAILED"}:
            _restore_artifact(artifact, state)
            return state

        _restore_artifact(artifact, state)
        for record in state.steps:
            if record.status == "RUNNING":
                record.status = "PENDING"
                record.error = "Execução interrompida; passo reagendado na retomada."
        state.status = "RUNNING"
        artifact.agentic_run_id = state.run_id
        artifact.execution_plan = state.plan
        self.state_store.save(state)
        return self._execute(artifact, state)

    def _execute(
        self,
        artifact: FileAnalysisArtifact,
        state: RunState,
    ) -> RunState:
        while state.status == "RUNNING":
            record = _next_pending_record(state)
            if record is None:
                decision = self.evaluator.evaluate_completion(state, artifact)
                self._apply_decision(state, artifact, decision)
                continue

            planned_step = next(
                step for step in state.plan.steps if step.id == record.step_id
            )
            state.current_step_id = record.step_id
            if not _dependencies_completed(state, planned_step):
                record.status = "SKIPPED"
                record.error = "Dependências não concluídas."
                self._apply_decision(
                    state,
                    artifact,
                    EvaluationDecision(
                        action="ESCALATE",
                        target_step_id=record.step_id,
                        reason="Plano inválido: dependências não concluídas.",
                    ),
                )
                continue

            record.status = "RUNNING"
            record.attempts += 1
            record.started_at = _now()
            self.state_store.save(state)

            failed = False
            try:
                self.orchestrator.run_capability(record.capability, artifact)
                record.status = "COMPLETED"
                record.error = None
            except Exception as exc:
                failed = True
                record.status = "FAILED"
                record.error = str(exc)
            record.finished_at = _now()
            state.artifact_snapshot = artifact.model_dump(mode="json")
            self.state_store.save(state)

            decision = self.evaluator.evaluate_step(
                state,
                artifact,
                step_failed=failed,
            )
            self._apply_decision(state, artifact, decision)

        artifact.agentic_decisions = [
            decision.model_dump(mode="json") for decision in state.decisions
        ]
        artifact.agentic_run_status = state.status
        state.artifact_snapshot = artifact.model_dump(mode="json")
        self.state_store.save(state)
        return state

    def _apply_decision(self, state, artifact, decision) -> None:
        state.decisions.append(decision)

        if decision.action == "RETRY":
            record = next(
                item for item in state.steps if item.step_id == decision.target_step_id
            )
            record.status = "PENDING"
        elif decision.action == "CORRECT":
            if state.correction_cycles >= self.MAX_CORRECTION_CYCLES:
                self._escalate(
                    state,
                    artifact,
                    "Limite de ciclos de correção atingido.",
                )
            else:
                state.correction_cycles += 1
                self._append_correction_steps(state, decision.correction_capabilities)
                artifact.execution_plan = state.plan
        elif decision.action == "COMPLETE":
            state.status = "COMPLETED"
        elif decision.action == "ESCALATE":
            self._escalate(state, artifact, decision.reason)

        state.artifact_snapshot = artifact.model_dump(mode="json")
        self.state_store.save(state)

    @staticmethod
    def _escalate(
        state: RunState,
        artifact: FileAnalysisArtifact,
        reason: str,
    ) -> None:
        state.status = "ESCALATED"
        artifact.test_generation_recommendation = "SKIPPED"
        artifact.add_policy("agentic_human_escalation")
        artifact.add_note(f"Escalação agêntica: {reason}")

    @staticmethod
    def _append_correction_steps(
        state: RunState,
        capabilities: list[CapabilityName],
    ) -> None:
        previous_id = state.steps[-1].step_id if state.steps else None
        for index, capability in enumerate(capabilities, start=1):
            step_id = f"correction-{state.correction_cycles}-{index}"
            plan_step = PlanStep(
                id=step_id,
                capability=capability,
                reason="Correção autorizada pelo evaluator determinístico.",
                depends_on=[previous_id] if previous_id else [],
                max_attempts=2,
            )
            state.plan.steps.append(plan_step)
            state.steps.append(
                StepExecutionRecord(
                    step_id=step_id,
                    capability=capability,
                )
            )
            previous_id = step_id


def _next_pending_record(state: RunState) -> StepExecutionRecord | None:
    return next((record for record in state.steps if record.status == "PENDING"), None)


def _dependencies_completed(state: RunState, step: PlanStep) -> bool:
    statuses = {record.step_id: record.status for record in state.steps}
    return all(statuses.get(dependency) == "COMPLETED" for dependency in step.depends_on)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _restore_artifact(
    artifact: FileAnalysisArtifact,
    state: RunState,
) -> None:
    if not state.artifact_snapshot:
        return
    restored = FileAnalysisArtifact.model_validate(state.artifact_snapshot)
    for field_name in FileAnalysisArtifact.model_fields:
        setattr(artifact, field_name, getattr(restored, field_name))
