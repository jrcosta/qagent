from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from src.config.settings import Settings
from src.crew.cooperative_analysis_crew import CooperativeAnalysisCrewRunner
from src.crew.high_risk_strategy_crew import HighRiskTestStrategyRunner
from src.crew.planning_crew import PlannerCrewRunner
from src.crew.qa_crew import QACrewRunner
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.schemas.review_result import ReviewResult
from src.services.agentic_runtime import GovernedAgenticRuntime
from src.services.analysis_orchestrator import AnalysisOrchestrator
from src.services.artifact_exporter import (
    export_artifacts_to_json,
    export_run_summary,
)
from src.services.project_knowledge_indexer import index_project_knowledge
from src.services.run_state_store import JsonRunStateStore
from src.services.token_budget_planner import (
    TokenBudgetPlanner,
    build_code_content_for_plan,
)
from src.utils.git_utils import get_changed_files, get_file_diff


@dataclass
class AnalysisPipelineResult:
    artifacts: list[FileAnalysisArtifact]
    report_file: Path
    artifacts_file: Path
    summary_file: Path


class RepositoryAnalysisPipeline:
    """Serviço reutilizável para análise completa de um repositório."""

    def __init__(
        self,
        settings: Settings,
        *,
        qa_runner: QACrewRunner | None = None,
        cooperative_runner: CooperativeAnalysisCrewRunner | None = None,
        high_risk_runner: HighRiskTestStrategyRunner | None = None,
    ) -> None:
        self.settings = settings
        self.qa_runner = qa_runner or QACrewRunner(settings)
        self.cooperative_runner = (
            cooperative_runner or CooperativeAnalysisCrewRunner(settings)
        )
        self.high_risk_runner = high_risk_runner or HighRiskTestStrategyRunner(
            settings
        )
        self.orchestrator = AnalysisOrchestrator(self.high_risk_runner)
        self.token_budget_planner = TokenBudgetPlanner()

    def run(
        self,
        *,
        repo_path: str | Path,
        output_file: str | Path,
        base_sha: str | None = None,
        head_sha: str | None = None,
        cooperative_analysis: bool = False,
        agentic_runtime: bool = False,
        run_state_dir: str | Path | None = None,
    ) -> AnalysisPipelineResult:
        repo = Path(repo_path).resolve()
        report_path = Path(output_file)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()

        index_project_knowledge(str(repo))
        planner = PlannerCrewRunner(self.settings) if agentic_runtime else None
        runtime = (
            GovernedAgenticRuntime(
                orchestrator=self.orchestrator,
                state_store=JsonRunStateStore(
                    run_state_dir or report_path.parent / "run_states" / "analysis"
                ),
            )
            if agentic_runtime
            else None
        )

        changed_files = get_changed_files(repo, base_sha, head_sha)
        artifacts: list[FileAnalysisArtifact] = []
        sections: list[str] = []

        for file_path in changed_files:
            code_content = read_file_content(repo, file_path)
            file_diff = get_file_diff(file_path, repo, base_sha, head_sha)
            if not file_diff.strip():
                continue

            budget = self.token_budget_planner.plan(
                file_path=file_path,
                file_diff=file_diff,
                code_content=code_content,
                cooperative_requested=cooperative_analysis,
            )
            prompt_code = build_code_content_for_plan(
                code_content,
                file_diff,
                budget,
            )
            crew_result, cooperative_succeeded, cooperative_error = (
                self._run_qa(
                    file_path=file_path,
                    file_diff=file_diff,
                    code_content=prompt_code,
                    repo_path=repo,
                    budget=budget,
                )
            )

            artifact = FileAnalysisArtifact(
                file_path=file_path,
                context_result=crew_result.context_result,
                token_budget_plan=budget,
                raw_review_markdown=crew_result.raw_review_markdown,
                review_result=crew_result.review_result,
            )
            self._record_qa_metadata(
                artifact,
                crew_result,
                cooperative_analysis,
                cooperative_succeeded,
                cooperative_error,
            )

            if planner and runtime:
                plan = planner.plan(artifact)
                artifact.add_policy(f"planner_{plan.planner_source}")
                artifact.add_note(f"Planner: {plan.rationale}")
                state = runtime.run(artifact, plan)
                artifact.add_policy("governed_agentic_runtime")
                artifact.add_note(
                    f"RunState {state.run_id} finalizado como {state.status}."
                )
            else:
                self.orchestrator.run_artifact_pipeline(artifact)

            artifacts.append(artifact)
            sections.append(
                f"# Arquivo analisado: {file_path}\n\n"
                f"{artifact.raw_review_markdown or ''}"
            )

        report = build_report(sections) if sections else (
            "# Nenhum arquivo alterado relevante encontrado para análise."
        )
        report_path.write_text(report, encoding="utf-8")
        artifacts_file = export_artifacts_to_json(
            artifacts,
            str(report_path.parent),
        )
        summary_file = export_run_summary(
            artifacts,
            str(report_path.parent),
            (time.perf_counter() - started) * 1000,
        )
        return AnalysisPipelineResult(
            artifacts=artifacts,
            report_file=report_path,
            artifacts_file=artifacts_file,
            summary_file=summary_file,
        )

    def _run_qa(
        self,
        *,
        file_path: str,
        file_diff: str,
        code_content: str,
        repo_path: Path,
        budget,
    ):
        started = time.perf_counter()
        cooperative_succeeded = False
        cooperative_error = ""

        if budget.analysis_mode == "skip":
            markdown = build_skipped_review_markdown(file_path, budget.reason)
            result = type(
                "SkippedQACrewResult",
                (),
                {
                    "raw_review_markdown": markdown,
                    "review_result": ReviewResult(
                        summary=(
                            "Mudança trivial analisada por fallback determinístico "
                            f"para {file_path}."
                        ),
                        findings=[],
                        test_needs=[],
                    ),
                    "context_result": None,
                },
            )()
        elif budget.analysis_mode == "cooperative":
            try:
                result = self.cooperative_runner.run(
                    file_path=file_path,
                    file_diff=file_diff,
                    code_content=code_content,
                    repo_path=str(repo_path),
                    token_budget_plan=budget,
                )
                cooperative_succeeded = True
            except Exception as exc:
                cooperative_error = str(exc)
                result = self.qa_runner.run(
                    file_path=file_path,
                    file_diff=file_diff,
                    code_content=code_content,
                    repo_path=str(repo_path),
                    token_budget_plan=budget,
                )
        else:
            result = self.qa_runner.run(
                file_path=file_path,
                file_diff=file_diff,
                code_content=code_content,
                repo_path=str(repo_path),
                token_budget_plan=budget,
            )
        result.qa_duration_ms = (time.perf_counter() - started) * 1000
        return result, cooperative_succeeded, cooperative_error

    @staticmethod
    def _record_qa_metadata(
        artifact,
        crew_result,
        cooperative_requested,
        cooperative_succeeded,
        cooperative_error,
    ) -> None:
        budget = artifact.token_budget_plan
        artifact.add_policy(f"token_budget_{budget.analysis_mode}")
        artifact.add_policy(f"context_{budget.context_level}")
        artifact.add_note(budget.reason)
        artifact.record_duration("qa_review", crew_result.qa_duration_ms)

        if getattr(crew_result, "structured_output_used", False):
            artifact.add_policy("qa_structured_output")
        elif getattr(crew_result, "output_fallback_reason", ""):
            artifact.add_fallback("qa_markdown_parser")
            artifact.add_note(crew_result.output_fallback_reason)

        if budget.analysis_mode == "skip":
            artifact.mark_step_skipped("qa_review", budget.reason)
            artifact.mark_step_executed("deterministic_token_saver_review")
        else:
            artifact.mark_step_executed("qa_review")

        if cooperative_succeeded:
            artifact.add_policy("cooperative_analysis_experimental")
            artifact.mark_step_executed("cooperative_analysis")
            artifact.agent_messages = crew_result.agent_messages
        elif cooperative_requested and budget.analysis_mode == "cooperative":
            artifact.add_fallback("cooperative_analysis_to_qa_agent")
            artifact.mark_step_skipped(
                "cooperative_analysis",
                cooperative_error or "erro não informado",
            )
        elif cooperative_requested:
            artifact.mark_step_skipped(
                "cooperative_analysis",
                f"{budget.analysis_mode} definido pelo TokenBudgetPlanner",
            )


def read_file_content(repo_path: Path, file_path: str) -> str:
    resolved = (repo_path / file_path).resolve()
    if not resolved.is_relative_to(repo_path.resolve()):
        raise ValueError(f"Path traversal blocked: {file_path}")
    if not resolved.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {resolved}")
    return resolved.read_text(encoding="utf-8")


def build_report(sections: list[str]) -> str:
    return "\n\n---\n\n".join(sections)


def build_skipped_review_markdown(file_path: str, reason: str) -> str:
    return (
        "# Resumo da análise\n"
        "Mudança trivial analisada por fallback determinístico.\n\n"
        "# Riscos identificados\n"
        "- Nenhum risco relevante identificado.\n\n"
        "# Necessidades de teste\n"
        "- Nenhuma necessidade adicional identificada.\n\n"
        f"Arquivo: {file_path}\nMotivo: {reason}"
    )

