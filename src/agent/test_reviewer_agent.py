from pathlib import Path

from crewai import Agent, LLM

from src.config.settings import Settings


class TestReviewerAgentFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        prompt_path = Path("src/prompts/test_reviewer_prompt.txt")
        if not prompt_path.exists():
            # Fallback se o arquivo não existir por algum motivo durante o desenvolvimento
            return "Você é um revisor crítico de testes automatizados."
        return prompt_path.read_text(encoding="utf-8")

    def create(self) -> Agent:
        llm = LLM(
            model=self.settings.llm_model,
            api_key=self.settings.llm_api_key,
            temperature=0.0,  # Revisão crítica requer consistência e baixa criatividade
        )

        return Agent(
            role="Revisor Crítico de Testes",
            goal=(
                "Analisar criticamente os testes gerados, validando sua coerência com o código original, "
                "cobertura de riscos e qualidade técnica geral."
            ),
            backstory=self.system_prompt,
            llm=llm,
            verbose=True,
            allow_delegation=False,
        )
