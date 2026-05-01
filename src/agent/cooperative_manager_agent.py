from crewai import Agent, LLM

from src.config.settings import Settings


class CooperativeManagerAgentFactory:
    """Factory do gerente que coordena uma análise multiagente cooperativa."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(self, tools: list | None = None) -> Agent:
        llm = LLM(
            model=self.settings.llm_model,
            api_key=self.settings.llm_api_key,
            temperature=0.0,
        )

        return Agent(
            role="Gerente de Qualidade e Coordenação Multiagente",
            goal=(
                "Ler todas as mensagens publicadas pelos agentes especializados no barramento "
                "e consolidar uma análise final objetiva, rastreável e útil para revisão humana."
            ),
            backstory=(
                "Você é um líder técnico de qualidade. Seu trabalho é consolidar o raciocínio "
                "dos especialistas, confrontar conclusões frágeis e produzir uma resposta "
                "final sem esconder incertezas. Você não substitui as regras determinísticas do "
                "QAgent; você melhora a qualidade da análise que alimenta essas regras. "
                "Use a ferramenta read_messages com topic='all' para acessar o que cada agente publicou."
            ),
            llm=llm,
            verbose=True,
            allow_delegation=False,
            tools=tools or [],
        )
