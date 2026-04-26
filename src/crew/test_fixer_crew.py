from crewai import Crew, Process

from src.agent.test_fixer_agent import TestFixerAgentFactory
from src.config.settings import Settings
from src.tasks.test_fixer_task import TestFixerTaskFactory


class TestFixerCrewRunner:
    """Runner responsável por corrigir testes gerados com base no CI."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(
        self,
        file_path: str,
        code_content: str,
        generated_tests: str,
        review_summary: str,
        ci_execution_summary: str,
    ) -> str:
        agent = TestFixerAgentFactory(self.settings).create()
        task = TestFixerTaskFactory.create(
            agent=agent,
            file_path=file_path,
            code_content=code_content,
            generated_tests=generated_tests,
            review_summary=review_summary,
            ci_execution_summary=ci_execution_summary,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )
        result = crew.kickoff()

        if hasattr(result, "tasks_output") and result.tasks_output:
            task_output = result.tasks_output[-1]
            if hasattr(task_output, "raw") and task_output.raw:
                return task_output.raw

        if hasattr(result, "raw") and result.raw:
            return result.raw

        return str(result)
