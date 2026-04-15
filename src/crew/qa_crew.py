from pathlib import Path

from crewai import Crew, Process

from src.agent.qa_agent import QAAgentFactory
from src.config.settings import Settings
from src.tasks.qa_task import QATaskFactory
from src.tools.repo_tools import RepoTools


class QACrewRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, file_path: str, file_diff: str, code_content: str, repo_path: str) -> str:
        repo_tools = RepoTools(Path(repo_path))

        tools = [
            repo_tools.read_file,
            repo_tools.search_in_repo,
            repo_tools.list_files_in_repo,
            repo_tools.find_related_test_files,
        ]

        agent = QAAgentFactory(self.settings).create(tools=tools)
        task = QATaskFactory.create(agent, file_path, file_diff, code_content)

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