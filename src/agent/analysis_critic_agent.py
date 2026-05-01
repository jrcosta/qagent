from crewai import Agent, LLM

from src.config.settings import Settings


class AnalysisCriticAgentFactory:
    """Factory do agente que critica a qualidade da análise antes da consolidação."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(self, tools: list | None = None) -> Agent:
        llm = LLM(
            model=self.settings.llm_model,
            api_key=self.settings.llm_api_key,
            temperature=0.0,
        )

        return Agent(
            role="Crítico de Análise de QA",
            goal=(
                "Revisar a análise de QA e a estratégia proposta para remover achados "
                "genéricos, identificar conclusões sem evidência e destacar incertezas reais."
            ),
            backstory=(
                "Você é um revisor técnico criterioso. Seu foco não é gerar testes, mas "
                "validar se a análise está bem fundamentada no diff, no código e no contexto "
                "do repositório. Você ajuda o gerente a consolidar uma resposta mais precisa."
            ),
            llm=llm,
            verbose=True,
            allow_delegation=False,
            tools=tools or [],
        )
