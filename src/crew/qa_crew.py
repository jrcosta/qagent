from src.agent.qa_agent import QAAgentFactory
from src.config.settings import Settings
from src.services.context_builder import RepoContextBuilder
from dataclasses import dataclass
from src.tasks.qa_task import QATaskFactory
from crewai import Crew, Process
from src.schemas.review_result import ReviewResult, parse_review_markdown_to_review_result


@dataclass
class QACrewResult:
    raw_review_markdown: str
    review_result: ReviewResult


class QACrewRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, file_path: str, file_diff: str, code_content: str, repo_path: str) -> QACrewResult:
        context_builder = RepoContextBuilder(repo_path)
        repo_context = context_builder.build(
            changed_file=file_path,
            code_content=code_content,
        )

        agent = QAAgentFactory(self.settings).create()
        task = QATaskFactory.create(
            agent=agent,
            file_path=file_path,
            file_diff=file_diff,
            code_content=code_content,
            repo_context=repo_context,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )

        result = crew.kickoff()

        raw_result = ""
        if hasattr(result, "tasks_output") and result.tasks_output:
            task_output = result.tasks_output[-1]
            if hasattr(task_output, "raw") and task_output.raw:
                raw_result = task_output.raw

        if not raw_result:
            if hasattr(result, "raw") and result.raw:
                raw_result = result.raw
            else:
                raw_result = str(result)

        review_result_parsed = parse_review_markdown_to_review_result(raw_result)

        return QACrewResult(
            raw_review_markdown=raw_result,
            review_result=review_result_parsed
        )