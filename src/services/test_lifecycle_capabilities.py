from __future__ import annotations

import time
from pathlib import Path

from src.config.settings import Settings
from src.crew.test_fixer_crew import TestFixerCrewRunner
from src.crew.test_generator_crew import TestGeneratorCrewRunner
from src.crew.test_reviewer_crew import TestReviewerCrewRunner
from src.schemas.agentic_runtime import CapabilityName
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.schemas.test_strategy_result import render_test_strategy_result_for_prompt
from src.services.test_execution_runner import TestExecutionRunner
from src.services.token_budget_planner import (
    TokenBudgetPlanner,
    build_code_content_for_plan,
)
from src.utils.git_utils import get_file_diff
from src.utils.pr_utils import parse_test_files_from_output, write_test_files


class TestLifecycleCapabilityExecutor:
    """Executa capabilities locais do ciclo de testes sobre um único artefato."""

    def __init__(
        self,
        *,
        settings: Settings,
        repo_path: str | Path,
        base_sha: str | None = None,
        head_sha: str | None = None,
        generator: TestGeneratorCrewRunner | None = None,
        reviewer: TestReviewerCrewRunner | None = None,
        fixer: TestFixerCrewRunner | None = None,
        execution_runner: TestExecutionRunner | None = None,
    ) -> None:
        self.settings = settings
        self.repo_path = Path(repo_path).resolve()
        self.base_sha = base_sha
        self.head_sha = head_sha
        self.generator = generator or TestGeneratorCrewRunner(settings)
        self.reviewer = reviewer or TestReviewerCrewRunner(settings)
        self.fixer = fixer or TestFixerCrewRunner(settings)
        self.execution_runner = execution_runner or TestExecutionRunner(
            repo_path=str(self.repo_path)
        )
        self.token_budget_planner = TokenBudgetPlanner()

    def run_capability(
        self,
        capability: CapabilityName,
        artifact: FileAnalysisArtifact,
    ) -> None:
        handlers = {
            "generate_tests": self._generate_tests,
            "write_tests": self._write_tests,
            "execute_tests": self._execute_tests,
            "review_tests": self._review_tests,
            "fix_tests": self._fix_tests,
        }
        handler = handlers.get(capability)
        if handler is None:
            raise ValueError(
                f"capability não suportada pelo ciclo de testes: {capability}"
            )
        handler(artifact)

    def _generate_tests(self, artifact: FileAnalysisArtifact) -> None:
        self._require_analysis_contracts(artifact)
        code_content = self._read_source(artifact)
        file_diff = self._get_diff(artifact)
        plan = artifact.token_budget_plan
        if plan is None:
            plan = self.token_budget_planner.plan(
                file_path=artifact.file_path,
                file_diff=file_diff,
                code_content=code_content,
            )
            artifact.token_budget_plan = plan

        prompt_code = build_code_content_for_plan(
            code_content=code_content,
            file_diff=file_diff,
            plan=plan,
        )
        started = time.perf_counter()
        output = self.generator.run(
            qa_report=artifact.raw_review_markdown or "",
            file_path=artifact.file_path,
            code_content=prompt_code,
            repo_path=str(self.repo_path),
            test_strategy=artifact.test_strategy_result,
            review_result=artifact.review_result,
            token_budget_plan=plan,
            risk_level=artifact.risk_level,
        )
        test_files = parse_test_files_from_output(output)
        if not test_files:
            raise ValueError("gerador não retornou arquivos de teste válidos")

        artifact.generated_tests_raw = output
        artifact.generated_test_files = test_files
        if artifact.context_result is None:
            artifact.context_result = self.generator.last_context_result
        artifact.memory_query = self.generator.last_memory_query
        artifact.memories_used_raw = self.generator.last_memories_raw
        artifact.memories_used = self.generator.last_memories_used
        artifact.record_duration(
            "test_generation",
            (time.perf_counter() - started) * 1000,
        )
        artifact.mark_step_executed("test_generation")

    def _write_tests(self, artifact: FileAnalysisArtifact) -> None:
        if not artifact.generated_test_files:
            raise ValueError("não há arquivos de teste para persistir")
        created = write_test_files(self.repo_path, artifact.generated_test_files)
        artifact.mark_step_executed("test_write")
        artifact.add_note(
            f"{len(created)} arquivo(s) de teste persistido(s) localmente."
        )

    def _execute_tests(self, artifact: FileAnalysisArtifact) -> None:
        started = time.perf_counter()
        result = self.execution_runner.run()
        artifact.test_execution_result = result
        artifact.record_duration(
            "test_execution",
            (time.perf_counter() - started) * 1000,
        )
        artifact.mark_step_executed("test_execution")
        if not result.success:
            artifact.add_note(
                f"Execução de testes falhou com exit_code={result.exit_code}."
            )

    def _review_tests(self, artifact: FileAnalysisArtifact) -> None:
        self._require_analysis_contracts(artifact)
        if not artifact.generated_test_files and not artifact.generated_tests_raw:
            raise ValueError("testes gerados ausentes para revisão")

        code_content = self._read_source(artifact)
        strategy = render_test_strategy_result_for_prompt(
            artifact.test_strategy_result
        )
        generated = artifact.generated_tests_raw or render_generated_test_files(
            artifact.generated_test_files
        )
        execution_summary = render_execution_result_for_prompt(
            artifact.test_execution_result
        )
        started = time.perf_counter()
        result = self.reviewer.run(
            file_path=artifact.file_path,
            code_content=code_content,
            qa_report=artifact.raw_review_markdown or "",
            test_strategy=strategy,
            generated_tests=generated,
            file_diff=self._get_diff(artifact),
            ci_execution_summary=execution_summary,
        )
        artifact.generated_test_review_result = result
        artifact.record_duration(
            "test_review",
            (time.perf_counter() - started) * 1000,
        )
        artifact.mark_step_executed("test_review")

    def _fix_tests(self, artifact: FileAnalysisArtifact) -> None:
        self._require_analysis_contracts(artifact)
        review = artifact.generated_test_review_result
        if review is None:
            raise ValueError("revisão ausente para correção")

        started = time.perf_counter()
        output = self.fixer.run(
            file_path=artifact.file_path,
            code_content=self._read_source(artifact),
            test_strategy=render_test_strategy_result_for_prompt(
                artifact.test_strategy_result
            ),
            failed_tests=(
                artifact.generated_tests_raw
                or render_generated_test_files(artifact.generated_test_files)
            ),
            review_report=render_review_report_for_fixer(artifact),
        )
        fixed_files = parse_test_files_from_output(output)
        if not fixed_files:
            raise ValueError("fixer não retornou arquivos corrigidos válidos")

        write_test_files(self.repo_path, fixed_files)
        artifact.generated_tests_raw = output
        artifact.generated_test_files = fixed_files
        artifact.record_duration(
            "test_auto_fix",
            (time.perf_counter() - started) * 1000,
        )
        artifact.mark_step_executed("test_auto_fix")
        artifact.add_note("Testes corrigidos e persistidos pelo runtime agêntico.")

    def _read_source(self, artifact: FileAnalysisArtifact) -> str:
        source = (self.repo_path / artifact.file_path).resolve()
        if not source.is_relative_to(self.repo_path):
            raise ValueError("arquivo fonte resolve fora do repositório")
        if not source.exists():
            raise FileNotFoundError(f"arquivo fonte não encontrado: {source}")
        return source.read_text(encoding="utf-8")

    def _get_diff(self, artifact: FileAnalysisArtifact) -> str:
        return get_file_diff(
            file_path=artifact.file_path,
            repo_path=self.repo_path,
            base_sha=self.base_sha,
            head_sha=self.head_sha,
        )

    @staticmethod
    def _require_analysis_contracts(artifact: FileAnalysisArtifact) -> None:
        if artifact.review_result is None:
            raise ValueError("ReviewResult ausente")
        if artifact.test_strategy_result is None:
            raise ValueError("TestStrategyResult ausente")


def render_generated_test_files(test_files: dict[str, str]) -> str:
    return "\n\n".join(
        f"### FILE: {path}\n```\n{content}\n```"
        for path, content in test_files.items()
    )


def render_execution_result_for_prompt(execution_result) -> str:
    if execution_result is None:
        return ""
    return (
        f"- success: {execution_result.success}\n"
        f"- command: `{execution_result.command}`\n"
        f"- exit_code: {execution_result.exit_code}\n"
        f"- duration_seconds: {execution_result.duration_seconds:.2f}\n\n"
        f"### stdout\n```text\n{_truncate(execution_result.stdout)}\n```\n\n"
        f"### stderr\n```text\n{_truncate(execution_result.stderr)}\n```"
    )


def render_review_report_for_fixer(
    artifact: FileAnalysisArtifact,
) -> str:
    review = artifact.generated_test_review_result
    if review is None:
        return "Revisão indisponível."

    lines = [
        f"STATUS: {review.status}",
        f"SUMMARY: {review.summary}",
        "ISSUES:",
    ]
    lines.extend(
        f"- [{issue.severity}] {issue.description} "
        f"(Fix: {issue.suggested_fix or 'N/A'})"
        for issue in review.issues
    )
    if review.missing_scenarios:
        lines.append("MISSING SCENARIOS:")
        lines.extend(f"- {scenario}" for scenario in review.missing_scenarios)
    if review.suggested_fixes:
        lines.append("SUGGESTED FIXES:")
        lines.extend(f"- {fix}" for fix in review.suggested_fixes)
    if artifact.test_execution_result:
        lines.append("REAL EXECUTION RESULT:")
        lines.append(
            render_execution_result_for_prompt(artifact.test_execution_result)
        )
    return "\n".join(lines)


def _truncate(value: str, limit: int = 6000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "\n... [conteúdo truncado]"
