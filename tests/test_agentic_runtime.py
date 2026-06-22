import json
from pathlib import Path

import pytest

from src.crew.planning_crew import (
    build_deterministic_plan,
    validate_plan_capabilities,
)
from src.schemas.agentic_runtime import (
    ExecutionPlan,
    PlanStep,
    RunState,
    StepExecutionRecord,
)
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.schemas.review_result import Finding, ReviewResult
from src.schemas.test_strategy_result import TestCase as StrategyTestCase
from src.schemas.test_strategy_result import TestStrategyResult as StrategyResult
from src.services.agentic_evaluator import AgenticRunEvaluator
from src.services.agentic_runtime import GovernedAgenticRuntime
from src.services.artifact_exporter import export_run_summary
from src.services.run_state_store import JsonRunStateStore


def _artifact(*, high_risk: bool = False) -> FileAnalysisArtifact:
    findings = (
        [Finding(description="Falha crítica", severity="ERROR")]
        if high_risk
        else []
    )
    return FileAnalysisArtifact(
        file_path="src/service.py",
        review_result=ReviewResult(
            summary="Mudança com contexto suficiente para avaliação.",
            findings=findings,
            test_needs=["Cobrir comportamento alterado"],
        ),
    )


class FakeOrchestrator:
    def __init__(self, fail_once: str | None = None) -> None:
        self.calls: list[str] = []
        self.fail_once = fail_once
        self.failed = False

    def run_capability(self, capability, artifact) -> None:
        self.calls.append(capability)
        if capability == self.fail_once and not self.failed:
            self.failed = True
            raise RuntimeError("falha transitória")

        if capability == "evaluate_risk":
            artifact.risk_level = (
                "HIGH"
                if artifact.review_result
                and any(f.severity == "ERROR" for f in artifact.review_result.findings)
                else "LOW"
            )
            artifact.review_quality = "OK"
            artifact.mark_step_executed("evaluate_risk")
        elif capability == "build_test_strategy":
            artifact.test_strategy_result = StrategyResult(
                recommended_tests=[
                    StrategyTestCase(
                        name="Cobrir comportamento alterado",
                        test_type="UNIT",
                        priority="HIGH" if artifact.risk_level == "HIGH" else "LOW",
                    )
                ]
            )
            artifact.mark_step_executed("build_strategy")
        elif capability == "enrich_high_risk":
            artifact.mark_step_executed("high_risk_enrichment")
        elif capability == "evaluate_final":
            artifact.test_generation_recommendation = "RECOMMENDED"
            artifact.mark_step_executed("evaluate_final")


def test_execution_plan_rejects_future_dependencies() -> None:
    with pytest.raises(ValueError, match="futuros/desconhecidos"):
        ExecutionPlan(
            objective="Analisar arquivo",
            rationale="Teste",
            steps=[
                PlanStep(
                    id="final",
                    capability="evaluate_final",
                    reason="Finalizar",
                    depends_on=["strategy"],
                ),
                PlanStep(
                    id="strategy",
                    capability="build_test_strategy",
                    reason="Construir",
                ),
            ],
        )


def test_catalog_validation_rejects_missing_capability_prerequisites() -> None:
    plan = ExecutionPlan(
        objective="Analisar arquivo",
        rationale="Plano incompleto",
        steps=[
            PlanStep(
                id="risk",
                capability="evaluate_risk",
                reason="Avaliar risco",
            ),
            PlanStep(
                id="enrich",
                capability="enrich_high_risk",
                reason="Enriquecer antes da estratégia",
                depends_on=["risk"],
            ),
            PlanStep(
                id="strategy",
                capability="build_test_strategy",
                reason="Construir estratégia tarde demais",
                depends_on=["enrich"],
            ),
            PlanStep(
                id="final",
                capability="evaluate_final",
                reason="Finalizar",
                depends_on=["strategy"],
            ),
        ],
    )

    with pytest.raises(ValueError, match="pré-requisitos"):
        validate_plan_capabilities(plan)


def test_catalog_validation_requires_governed_boundaries() -> None:
    plan = ExecutionPlan(
        objective="Analisar arquivo",
        rationale="Plano sem avaliação inicial",
        steps=[
            PlanStep(
                id="strategy",
                capability="build_test_strategy",
                reason="Construir estratégia",
            ),
            PlanStep(
                id="final",
                capability="evaluate_final",
                reason="Finalizar",
                depends_on=["strategy"],
            ),
        ],
    )

    with pytest.raises(ValueError, match="começar por evaluate_risk"):
        validate_plan_capabilities(plan)


def test_catalog_validation_requires_explicit_dependencies() -> None:
    plan = ExecutionPlan(
        objective="Analisar arquivo",
        rationale="Ordem correta, dependências ausentes",
        steps=[
            PlanStep(
                id="risk",
                capability="evaluate_risk",
                reason="Avaliar",
            ),
            PlanStep(
                id="strategy",
                capability="build_test_strategy",
                reason="Construir sem declarar dependência",
            ),
            PlanStep(
                id="final",
                capability="evaluate_final",
                reason="Finalizar",
                depends_on=["strategy"],
            ),
        ],
    )

    with pytest.raises(ValueError, match="dependências explícitas"):
        validate_plan_capabilities(plan)


def test_deterministic_planner_adds_high_risk_enrichment() -> None:
    plan = build_deterministic_plan(_artifact(high_risk=True))

    assert plan.planner_source == "deterministic_fallback"
    assert [step.capability for step in plan.steps] == [
        "evaluate_risk",
        "build_test_strategy",
        "enrich_high_risk",
        "evaluate_final",
    ]


def test_run_state_store_round_trip(tmp_path: Path) -> None:
    plan = build_deterministic_plan(_artifact())
    state = RunState(
        file_path="src/service.py",
        plan=plan,
        steps=[
            StepExecutionRecord(
                step_id=step.id,
                capability=step.capability,
            )
            for step in plan.steps
        ],
    )
    store = JsonRunStateStore(tmp_path)

    path = store.save(state)
    loaded = store.load(state.run_id)

    assert path.exists()
    assert loaded == state


def test_runtime_executes_plan_and_persists_completion(tmp_path: Path) -> None:
    artifact = _artifact()
    plan = build_deterministic_plan(artifact)
    orchestrator = FakeOrchestrator()
    store = JsonRunStateStore(tmp_path)
    runtime = GovernedAgenticRuntime(orchestrator, store)  # type: ignore[arg-type]

    state = runtime.run(artifact, plan)

    assert state.status == "COMPLETED"
    assert artifact.agentic_run_id == state.run_id
    assert artifact.execution_plan == plan
    assert orchestrator.calls == [
        "evaluate_risk",
        "build_test_strategy",
        "evaluate_final",
    ]
    assert store.load(state.run_id).status == "COMPLETED"
    assert state.decisions[-1].action == "COMPLETE"


def test_runtime_retries_transient_failure(tmp_path: Path) -> None:
    artifact = _artifact()
    plan = build_deterministic_plan(artifact)
    strategy_step = next(
        step for step in plan.steps if step.capability == "build_test_strategy"
    )
    strategy_step.max_attempts = 2
    orchestrator = FakeOrchestrator(fail_once="build_test_strategy")
    runtime = GovernedAgenticRuntime(
        orchestrator,  # type: ignore[arg-type]
        JsonRunStateStore(tmp_path),
    )

    state = runtime.run(artifact, plan)

    assert state.status == "COMPLETED"
    assert orchestrator.calls.count("build_test_strategy") == 2
    assert any(decision.action == "RETRY" for decision in state.decisions)


def test_runtime_escalates_after_retry_budget_is_exhausted(tmp_path: Path) -> None:
    artifact = _artifact()
    plan = build_deterministic_plan(artifact)
    orchestrator = FakeOrchestrator(fail_once="build_test_strategy")
    runtime = GovernedAgenticRuntime(
        orchestrator,  # type: ignore[arg-type]
        JsonRunStateStore(tmp_path),
    )

    state = runtime.run(artifact, plan)

    assert state.status == "ESCALATED"
    assert state.decisions[-1].action == "ESCALATE"
    assert artifact.agentic_run_status == "ESCALATED"
    assert artifact.test_generation_recommendation == "SKIPPED"
    assert "agentic_human_escalation" in artifact.applied_policies


def test_runtime_executes_authorized_correction_cycle(tmp_path: Path) -> None:
    artifact = _artifact(high_risk=True)
    plan = ExecutionPlan(
        objective="Analisar risco alto",
        rationale="Planner omitiu enriquecimento; evaluator deve corrigir.",
        steps=[
            PlanStep(
                id="risk",
                capability="evaluate_risk",
                reason="Avaliar risco",
            ),
            PlanStep(
                id="strategy",
                capability="build_test_strategy",
                reason="Construir estratégia",
                depends_on=["risk"],
            ),
            PlanStep(
                id="final",
                capability="evaluate_final",
                reason="Finalizar",
                depends_on=["strategy"],
            ),
        ],
    )
    orchestrator = FakeOrchestrator()
    runtime = GovernedAgenticRuntime(
        orchestrator,  # type: ignore[arg-type]
        JsonRunStateStore(tmp_path),
    )

    state = runtime.run(artifact, plan)

    assert state.status == "COMPLETED"
    assert state.correction_cycles == 1
    assert orchestrator.calls[-2:] == ["enrich_high_risk", "evaluate_final"]
    assert any(decision.action == "CORRECT" for decision in state.decisions)
    assert len(state.plan.steps) == 5


def test_runtime_resumes_from_persisted_snapshot(tmp_path: Path) -> None:
    persisted_artifact = _artifact()
    persisted_artifact.risk_level = "LOW"
    persisted_artifact.review_quality = "OK"
    persisted_artifact.mark_step_executed("evaluate_risk")
    plan = build_deterministic_plan(persisted_artifact)
    state = RunState(
        file_path=persisted_artifact.file_path,
        plan=plan,
        status="RUNNING",
        current_step_id="strategy",
        steps=[
            StepExecutionRecord(
                step_id="risk",
                capability="evaluate_risk",
                status="COMPLETED",
                attempts=1,
            ),
            StepExecutionRecord(
                step_id="strategy",
                capability="build_test_strategy",
                status="RUNNING",
                attempts=1,
            ),
            StepExecutionRecord(
                step_id="final",
                capability="evaluate_final",
                status="PENDING",
            ),
        ],
        artifact_snapshot=persisted_artifact.model_dump(mode="json"),
    )
    store = JsonRunStateStore(tmp_path)
    store.save(state)
    resumed_artifact = _artifact()
    orchestrator = FakeOrchestrator()
    runtime = GovernedAgenticRuntime(
        orchestrator,  # type: ignore[arg-type]
        store,
    )

    resumed = runtime.resume(resumed_artifact, state.run_id)

    assert resumed.status == "COMPLETED"
    assert orchestrator.calls == ["build_test_strategy", "evaluate_final"]
    assert "evaluate_risk" in resumed_artifact.executed_steps
    strategy_record = next(
        record for record in resumed.steps if record.step_id == "strategy"
    )
    assert strategy_record.attempts == 2


def test_evaluator_requests_correction_for_unenriched_high_risk() -> None:
    artifact = _artifact(high_risk=True)
    artifact.risk_level = "HIGH"
    artifact.review_quality = "OK"
    artifact.test_strategy_result = StrategyResult(
        recommended_tests=[
            StrategyTestCase(
                name="Cenário crítico",
                test_type="UNIT",
                priority="HIGH",
            )
        ]
    )
    artifact.test_generation_recommendation = "RECOMMENDED"
    plan = build_deterministic_plan(artifact)
    state = RunState(
        file_path=artifact.file_path,
        plan=plan,
        steps=[
            StepExecutionRecord(
                step_id=step.id,
                capability=step.capability,
                status="COMPLETED",
            )
            for step in plan.steps
        ],
    )

    decision = AgenticRunEvaluator().evaluate_completion(state, artifact)

    assert decision.action == "CORRECT"
    assert decision.correction_capabilities == [
        "enrich_high_risk",
        "evaluate_final",
    ]


def test_evaluator_escalates_incomplete_review() -> None:
    artifact = _artifact()
    artifact.review_quality = "INCOMPLETE"
    plan = build_deterministic_plan(artifact)
    state = RunState(file_path=artifact.file_path, plan=plan)

    decision = AgenticRunEvaluator().evaluate_completion(state, artifact)

    assert decision.action == "ESCALATE"
    assert "Review incompleto" in decision.reason


def test_run_summary_reports_agentic_terminal_status(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact.agentic_run_status = "COMPLETED"

    path = export_run_summary([artifact], str(tmp_path))
    summary = json.loads(path.read_text(encoding="utf-8"))

    assert summary["agentic_run_status_distribution"] == {"COMPLETED": 1}
