from src.agent.qa_agent import QAAgentFactory
from src.config.settings import Settings
from src.services.context_builder import RepoContextBuilder
from dataclasses import dataclass, field
from src.tasks.qa_task import QATaskFactory
from crewai import Crew, Process
from src.schemas.context_result import ContextResult
from src.schemas.review_result import (
    ReviewResult,
    parse_review_markdown_to_review_result,
    render_review_result_as_markdown,
)
from src.schemas.context_result import render_context_result_for_prompt
from src.schemas.token_budget import TokenBudgetPlan



@dataclass
class QACrewResult:
    raw_review_markdown: str
    review_result: ReviewResult
    context_result: ContextResult | None = None
    agent_messages: dict = field(default_factory=dict)
    structured_output_used: bool = False
    output_fallback_reason: str = ""


class QACrewRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(
        self,
        file_path: str,
        file_diff: str,
        code_content: str,
        repo_path: str,
        token_budget_plan: TokenBudgetPlan | None = None,
    ) -> QACrewResult:
        context_builder = RepoContextBuilder(repo_path)
        context_result = context_builder.build(
            changed_file=file_path,
            code_content=code_content,
            context_level=(
                token_budget_plan.context_level if token_budget_plan else "standard"
            ),
            max_context_chars=(
                token_budget_plan.max_context_chars if token_budget_plan else None
            ),
        )
        
        repo_context_text = render_context_result_for_prompt(context_result)

        agent = QAAgentFactory(self.settings).create()
        task = QATaskFactory.create(
            agent=agent,
            file_path=file_path,
            file_diff=file_diff,
            code_content=code_content,
            repo_context=repo_context_text,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )

        result = crew.kickoff()

        review_result, raw_result, structured_output_used, fallback_reason = (
            extract_review_result(result)
        )

        return QACrewResult(
            raw_review_markdown=(
                render_review_result_as_markdown(review_result)
                if structured_output_used
                else raw_result
            ),
            review_result=review_result,
            context_result=context_result,
            structured_output_used=structured_output_used,
            output_fallback_reason=fallback_reason,
        )


def extract_review_result(result) -> tuple[ReviewResult, str, bool, str]:
    """
    Extrai ReviewResult diretamente do output CrewAI.

    O Markdown legado só é interpretado quando o runtime não fornece saída
    Pydantic/JSON válida.
    """
    candidates = []
    if hasattr(result, "tasks_output") and result.tasks_output:
        candidates.append(result.tasks_output[-1])
    candidates.append(result)

    for candidate in candidates:
        pydantic_output = getattr(candidate, "pydantic", None)
        if pydantic_output is not None:
            try:
                return (
                    ReviewResult.model_validate(pydantic_output),
                    _extract_raw_result(result),
                    True,
                    "",
                )
            except Exception:
                pass

        json_output = getattr(candidate, "json_dict", None)
        if json_output:
            try:
                return (
                    ReviewResult.model_validate(json_output),
                    _extract_raw_result(result),
                    True,
                    "",
                )
            except Exception:
                pass

    raw_result = _extract_raw_result(result)
    return (
        parse_review_markdown_to_review_result(raw_result),
        raw_result,
        False,
        "CrewAI não retornou ReviewResult estruturado válido; Markdown interpretado.",
    )


def _extract_raw_result(result) -> str:
    if hasattr(result, "tasks_output") and result.tasks_output:
        task_output = result.tasks_output[-1]
        raw = getattr(task_output, "raw", None)
        if raw:
            return raw

    raw = getattr(result, "raw", None)
    if raw:
        return raw

    return str(result)
