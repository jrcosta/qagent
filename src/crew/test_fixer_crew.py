from crewai import Crew, Process
from src.agent.test_fixer_agent import TestFixerAgentFactory
from src.config.settings import Settings
from src.tasks.test_fixer_task import TestFixerTaskFactory

class TestFixerCrewRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(
        self,
        file_path: str,
        code_content: str,
        test_strategy: str,
        failed_tests: str,
        review_report: str,
    ) -> str:
        agent = TestFixerAgentFactory(self.settings).create()
        task = TestFixerTaskFactory.create(
            agent=agent,
            file_path=file_path,
            code_content=code_content,
            test_strategy=test_strategy,
            failed_tests=failed_tests,
            review_report=review_report,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )

        result = crew.kickoff()
        return str(result)
