from dataclasses import dataclass

from crewai import Crew, Process

from src.agent.analysis_critic_agent import AnalysisCriticAgentFactory
from src.agent.cooperative_manager_agent import CooperativeManagerAgentFactory
from src.agent.high_risk_strategy_agent import HighRiskStrategyAgentFactory
from src.agent.qa_agent import QAAgentFactory
from src.config.settings import Settings
from src.crew.qa_crew import QACrewResult
from src.schemas.context_result import render_context_result_for_prompt
from src.schemas.review_result import parse_review_markdown_to_review_result
from src.services.context_builder import RepoContextBuilder
from src.tasks.cooperative_analysis_task import CooperativeAnalysisTaskFactory


@dataclass
class CooperativeAnalysisMetadata:
    process: str = "hierarchical"
    manager_role: str = "Gerente de Qualidade e Coordenação Multiagente"
    agents: tuple[str, ...] = (
        "QA Sênior Investigador",
        "Especialista em Estratégia de Testes para Código de Alto Risco",
        "Crítico de Análise de QA",
    )


class CooperativeAnalysisCrewRunner:
    """
    Executa uma análise experimental com múltiplos agentes coordenados por gerente.

    Este runner não substitui o pipeline determinístico. Ele produz o markdown de
    QA inicial; `AnalysisOrchestrator` continua responsável por risco, estratégia,
    recomendação de geração e fallback determinístico.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.metadata = CooperativeAnalysisMetadata()

    def run(
        self,
        file_path: str,
        file_diff: str,
        code_content: str,
        repo_path: str,
    ) -> QACrewResult:
        context_builder = RepoContextBuilder(repo_path)
        context_result = context_builder.build(
            changed_file=file_path,
            code_content=code_content,
        )
        repo_context_text = render_context_result_for_prompt(context_result)

        manager_agent = CooperativeManagerAgentFactory(self.settings).create()
        qa_agent = QAAgentFactory(self.settings).create()
        strategy_agent = HighRiskStrategyAgentFactory(self.settings).create()
        critic_agent = AnalysisCriticAgentFactory(self.settings).create()

        task = CooperativeAnalysisTaskFactory.create(
            file_path=file_path,
            file_diff=file_diff,
            code_content=code_content,
            repo_context=repo_context_text,
        )

        crew = Crew(
            agents=[qa_agent, strategy_agent, critic_agent],
            tasks=[task],
            manager_agent=manager_agent,
            process=Process.hierarchical,
            verbose=True,
        )

        result = crew.kickoff()
        raw_result = self._extract_raw_result(result)
        review_result = parse_review_markdown_to_review_result(raw_result)

        return QACrewResult(
            raw_review_markdown=raw_result,
            review_result=review_result,
        )

    @staticmethod
    def _extract_raw_result(result) -> str:
        if hasattr(result, "tasks_output") and result.tasks_output:
            task_output = result.tasks_output[-1]
            if hasattr(task_output, "raw") and task_output.raw:
                return task_output.raw

        if hasattr(result, "raw") and result.raw:
            return result.raw

        return str(result)
