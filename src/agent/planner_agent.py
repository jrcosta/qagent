from crewai import Agent, LLM

from src.config.settings import Settings


class PlannerAgentFactory:
    """Cria o planejador limitado ao catálogo explícito de capacidades."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(self) -> Agent:
        llm = LLM(
            model=self.settings.llm_model,
            api_key=self.settings.llm_api_key,
            temperature=0.0,
        )
        return Agent(
            role="Planejador de Execução de QA",
            goal=(
                "Produzir um plano mínimo, válido e rastreável usando somente "
                "capacidades autorizadas pelo runtime."
            ),
            backstory=(
                "Você planeja, mas não executa código nem inventa ferramentas. "
                "Cada passo deve ter dependências explícitas e justificativa."
            ),
            llm=llm,
            verbose=True,
            allow_delegation=False,
        )

