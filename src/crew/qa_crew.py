from crewai import Crew, Process

from src.agent.qa_agent import QAAgentFactory
from src.config.settings import Settings
from src.tasks.qa_task import QATaskFactory


class QACrewRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, file_path: str, code_content: str) -> str:
        agent = QAAgentFactory(self.settings).create()
        task = QATaskFactory.create(agent, file_path, code_content)

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