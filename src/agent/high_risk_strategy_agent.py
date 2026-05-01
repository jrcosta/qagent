from crewai import Agent, LLM

from src.config.settings import Settings


class HighRiskStrategyAgentFactory:
    """Factory para criar o agente especializado em refinamento de estratégia de testes de alto risco."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(self, tools: list | None = None) -> Agent:
        llm = LLM(
            model=self.settings.llm_model,
            api_key=self.settings.llm_api_key,
            temperature=self.settings.llm_temperature,
        )

        return Agent(
            role="Especialista em Estratégia de Testes para Código de Alto Risco",
            goal=(
                "Refinar e enriquecer estratégias de teste para arquivos de alto risco, "
                "adicionando cenários críticos, reforçando regressão e melhorando a priorização "
                "com base na revisão de código e contexto do repositório."
            ),
            backstory=(
                "Você é um engenheiro de qualidade sênior especializado em análise de risco. "
                "Você recebe uma estratégia de testes base já construída e deve refiná-la, "
                "sem descartar o que já existe. Seu foco é garantir que nenhum cenário crítico "
                "seja esquecido e que a cobertura de regressão esteja adequada ao nível de risco."
            ),
            llm=llm,
            verbose=True,
            allow_delegation=False,
            tools=tools or [],
        )
