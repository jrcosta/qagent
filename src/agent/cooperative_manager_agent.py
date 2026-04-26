from crewai import Agent, LLM

from src.config.settings import Settings


class CooperativeManagerAgentFactory:
    """Factory do gerente que coordena uma análise multiagente cooperativa."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(self) -> Agent:
        llm = LLM(
            model=self.settings.llm_model,
            api_key=self.settings.llm_api_key,
            temperature=0.0,
        )

        return Agent(
            role="Gerente de Qualidade e Coordenação Multiagente",
            goal=(
                "Coordenar especialistas de QA, estratégia de testes e revisão crítica "
                "para produzir uma análise final objetiva, rastreável e útil para revisão humana."
            ),
            backstory=(
                "Você é um líder técnico de qualidade. Seu trabalho é distribuir o raciocínio "
                "entre especialistas, confrontar conclusões frágeis e consolidar uma resposta "
                "final sem esconder incertezas. Você não substitui as regras determinísticas do "
                "QAgent; você melhora a qualidade da análise que alimenta essas regras."
            ),
            llm=llm,
            verbose=True,
            allow_delegation=True,
        )
