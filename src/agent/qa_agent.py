from __future__ import annotations

from pathlib import Path
from typing import Optional

from crewai import Agent, LLM

from src.config.settings import Settings
from src.tools.repo_tools import (
    FindRelatedTestFilesTool,
    GetOfficialDocsReferenceTool,
    InspectRepoStackTool,
    ReadFileTool,
    SearchInRepoTool,
)

try:
    from src.utils.debug_logger import DebugLogger
except Exception:  # pragma: no cover
    DebugLogger = None  # type: ignore


class QAAgentFactory:
    def __init__(
        self,
        settings: Settings,
        repo_path: str,
        debug_logger: Optional[DebugLogger] = None,
    ) -> None:
        self.settings = settings
        self.repo_path = Path(repo_path)
        self.debug_logger = debug_logger
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        prompt_path = Path("src/prompts/system_prompt.txt")
        return prompt_path.read_text(encoding="utf-8")

    def create(self) -> Agent:
        llm = LLM(
            model=self.settings.llm_model,
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_base_url,
            temperature=self.settings.llm_temperature,
        )

        tools = [
            InspectRepoStackTool(self.repo_path, self.debug_logger),
            GetOfficialDocsReferenceTool(self.repo_path, self.debug_logger),
            ReadFileTool(self.repo_path, self.debug_logger),
            SearchInRepoTool(self.repo_path, self.debug_logger),
            FindRelatedTestFilesTool(self.repo_path, self.debug_logger),
        ]

        if self.debug_logger:
            self.debug_logger.write_json(
                "agent_config.json",
                {
                    "model": self.settings.llm_model,
                    "base_url": self.settings.llm_base_url,
                    "temperature": self.settings.llm_temperature,
                    "tools": [tool.name for tool in tools],
                    "repo_path": str(self.repo_path),
                },
            )

        return Agent(
            role="QA Sênior Investigador",
            goal=(
                "Revisar mudanças de código com profundidade, de forma agnóstica à stack, usando o diff, "
                "o conteúdo atual do arquivo, o contexto do repositório e tools para identificar inconsistências, "
                "riscos reais, regressões e testes relevantes."
            ),
            backstory=self.system_prompt,
            llm=llm,
            tools=tools,
            verbose=True,
            allow_delegation=False,
        )
