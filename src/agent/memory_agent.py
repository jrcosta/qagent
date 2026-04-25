"""Agent that summarises QAgent reviewer comments into lessons learned."""

from pathlib import Path

from crewai import Agent, LLM

from src.config.settings import Settings


class MemoryAgentFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(self) -> Agent:
        llm = LLM(
            model=self.settings.llm_model,
            api_key=self.settings.llm_api_key,
            temperature=0,
        )

        return Agent(
            role="Analista de Lições Aprendidas",
            goal=(
                "Extrair de um comentário de revisão crítica do QAgent "
                "as lições concretas sobre o que o agente gerador de testes unitários errou, "
                "para que esses erros não se repitam em execuções futuras."
            ),
            backstory=(
                "Você é um especialista em QA e melhoria contínua. "
                "Recebe comentários feitos em PRs de testes gerados automaticamente "
                "e extrai de forma clara e objetiva quais foram os erros ou problemas "
                "apontados pelo revisor. Cada lição deve ser uma frase curta e acionável "
                "que o agente gerador de testes possa seguir na próxima execução."
            ),
            llm=llm,
            verbose=True,
            allow_delegation=False,
        )
