from pathlib import Path

from crewai import Agent, LLM

from src.config.settings import Settings


class QAAgentFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        prompt_path = Path("src/prompts/system_prompt.txt")
        return prompt_path.read_text(encoding="utf-8")

    def create(self) -> Agent:
        llm = LLM(
            model=self.settings.llm_model,
            api_key=self.settings.llm_api_key,
            temperature=self.settings.llm_temperature,
        )

        return Agent(
            role="QA Sênior Investigador",
            goal=(
                "Analisar mudanças de código com profundidade usando diff, conteúdo do arquivo "
                "e contexto adicional do repositório para identificar riscos reais e testes relevantes"
            ),
            backstory=self.system_prompt,
            llm=llm,
            verbose=True,
            allow_delegation=False,
        )