from pathlib import Path

from crewai import Crew, Process

from src.agent.qa_agent import QAAgentFactory
from src.config.settings import Settings
from src.tasks.qa_task import QATaskFactory
from src.tools.repo_tools import (
    FindRelatedTestFilesTool,
    ListFilesInRepoTool,
    ReadFileTool,
    SearchInRepoTool,
)


class QACrewRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, file_path: str, file_diff: str, code_content: str, repo_path: str) -> str:
        repo_path_obj = Path(repo_path)

        tools = [
            ReadFileTool(repo_path_obj),
            SearchInRepoTool(repo_path_obj),
            ListFilesInRepoTool(repo_path_obj),
            FindRelatedTestFilesTool(repo_path_obj),
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