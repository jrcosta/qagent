from pathlib import Path

from crewai import Agent, LLM

from src.config.settings import Settings


class TestFixerAgentFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        prompt_path = Path("src/prompts/test_fixer_prompt.txt")
        if not prompt_path.exists():
            return "Você corrige testes gerados com base em falhas reais de CI."
        return prompt_path.read_text(encoding="utf-8")

    def create(self) -> Agent:
        llm = LLM(
            model=self.settings.llm_model,
            api_key=self.settings.llm_api_key,
            temperature=0.0,
        )

        return Agent(
            role="Corretor de Testes Gerados",
            goal=(
                "Corrigir testes automatizados gerados para que reflitam o contrato real "
                "do código e passem no CI do PR alvo."
            ),
            backstory=self.system_prompt,
            llm=llm,
            verbose=True,
            allow_delegation=False,
        )
