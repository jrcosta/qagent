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
from src.schemas.token_budget import TokenBudgetPlan
from src.services.context_builder import RepoContextBuilder
from src.tasks.cooperative_analysis_task import CooperativeAnalysisTaskFactory
from src.tools.messaging_tools import PublishMessageTool, ReadMessagesTool, get_bus


@dataclass
class CooperativeAnalysisMetadata:
    process: str = "sequential"
    agents: tuple[str, ...] = (
        "QA Sênior Investigador",
        "Especialista em Estratégia de Testes para Código de Alto Risco",
        "Crítico de Análise de QA",
        "Gerente de Qualidade e Coordenação Multiagente",
    )


class CooperativeAnalysisCrewRunner:
    """
    Executa análise cooperativa com 4 agentes sequenciais comunicando via barramento.

    Fluxo:
      1. QA Agent  → analisa diff → publica 'qa_findings' no barramento
      2. Strategy Agent → lê 'qa_findings' → publica 'test_strategy'
      3. Critic Agent → lê 'qa_findings' + 'test_strategy' → publica 'critique'
      4. Manager Agent → lê 'all' → consolida relatório final em Markdown

    O barramento (AgentMessageBus) é reiniciado antes de cada execução para
    evitar contaminação entre análises de arquivos distintos.
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
        token_budget_plan: TokenBudgetPlan | None = None,
    ) -> QACrewResult:
        get_bus().reset()

        context_builder = RepoContextBuilder(repo_path)
        context_result = context_builder.build(
            changed_file=file_path,
            code_content=code_content,
            context_level=(
                token_budget_plan.context_level if token_budget_plan else "standard"
            ),
            max_context_chars=(
                token_budget_plan.max_context_chars if token_budget_plan else None
            ),
        )
        repo_context_text = render_context_result_for_prompt(context_result)

        messaging_tools = [PublishMessageTool(), ReadMessagesTool()]

        qa_agent = QAAgentFactory(self.settings).create(tools=messaging_tools)
        strategy_agent = HighRiskStrategyAgentFactory(self.settings).create(tools=messaging_tools)
        critic_agent = AnalysisCriticAgentFactory(self.settings).create(tools=messaging_tools)
        manager_agent = CooperativeManagerAgentFactory(self.settings).create(tools=messaging_tools)

        qa_task = CooperativeAnalysisTaskFactory.create_qa_task(
            file_path=file_path,
            file_diff=file_diff,
            code_content=code_content,
            repo_context=repo_context_text,
        )
        qa_task.agent = qa_agent

        strategy_task = CooperativeAnalysisTaskFactory.create_strategy_task(file_path=file_path)
        strategy_task.agent = strategy_agent
        strategy_task.context = [qa_task]

        critic_task = CooperativeAnalysisTaskFactory.create_critic_task(file_path=file_path)
        critic_task.agent = critic_agent
        critic_task.context = [qa_task, strategy_task]

        consolidation_task = CooperativeAnalysisTaskFactory.create_consolidation_task(file_path=file_path)
        consolidation_task.agent = manager_agent
        consolidation_task.context = [qa_task, strategy_task, critic_task]

        crew = Crew(
            agents=[qa_agent, strategy_agent, critic_agent, manager_agent],
            tasks=[qa_task, strategy_task, critic_task, consolidation_task],
            process=Process.sequential,
            verbose=True,
        )

        result = crew.kickoff()
        raw_result = self._extract_raw_result(result)
        review_result = parse_review_markdown_to_review_result(raw_result)

        return QACrewResult(
            raw_review_markdown=raw_result,
            review_result=review_result,
            context_result=context_result,
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
