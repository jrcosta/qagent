
from __future__ import annotations

from pathlib import Path

from crewai import Agent

from src.tools.repo_tools import (
    FindRelatedTestFilesTool,
    GetOfficialDocsReferenceTool,
    InspectRepoStackTool,
    ReadFileTool,
    SearchInRepoTool,
)


class QAAgentFactory:
    def __init__(self, settings, repo_path: str, debug_logger=None) -> None:
        self.settings = settings
        self.repo_path = repo_path
        self.debug_logger = debug_logger

    def create(self) -> Agent:
        tools = [
            ReadFileTool(repo_path=self.repo_path, debug_logger=self.debug_logger),
            SearchInRepoTool(repo_path=self.repo_path, debug_logger=self.debug_logger),
            FindRelatedTestFilesTool(repo_path=self.repo_path, debug_logger=self.debug_logger),
            InspectRepoStackTool(repo_path=self.repo_path, debug_logger=self.debug_logger),
            GetOfficialDocsReferenceTool(),
        ]

        if self.debug_logger:
            self.debug_logger.write_json(
                "agent_config.json",
                {
                    "repo_path": self.repo_path,
                    "tools": [tool.name for tool in tools],
                },
            )

        return Agent(
            role="Agnostic Code Reviewer",
            goal=(
                "Review code changes critically, identify concrete inconsistencies, "
                "possible regressions, contract breaks, fragile behavior and missing validation."
            ),
            backstory=(
                "You are a senior QA-oriented reviewer who can assess code changes across "
                "different languages, frameworks and project structures. You do not assume a specific "
                "stack. You inspect the repository, use tools when necessary, and ground every important "
                "claim in evidence from the diff, related code, tests or official documentation."
            ),
            tools=tools,
            llm=self.settings.llm,
            verbose=True,
            allow_delegation=False,
        )
