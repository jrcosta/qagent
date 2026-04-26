from crewai import Crew, Process
from src.agent.test_reviewer_agent import TestReviewerAgentFactory
from src.config.settings import Settings
from src.schemas.generated_test_review_result import GeneratedTestsReviewResult
from src.tasks.test_reviewer_task import TestReviewerTaskFactory


class TestReviewerCrewRunner:
    """
    Runner para a Crew especializada em revisão crítica de testes gerados.
    """
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(
        self,
        file_path: str,
        code_content: str,
        qa_report: str,
        test_strategy: str,
        generated_tests: str,
        file_diff: str = "",
        ci_execution_summary: str = "",
    ) -> GeneratedTestsReviewResult:
        agent = TestReviewerAgentFactory(self.settings).create()
        task = TestReviewerTaskFactory.create(
            agent=agent,
            file_path=file_path,
            code_content=code_content,
            qa_report=qa_report,
            test_strategy=test_strategy,
            generated_tests=generated_tests,
            file_diff=file_diff,
            ci_execution_summary=ci_execution_summary,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )

        result = crew.kickoff()

        # Tenta extrair o resultado estruturado do Crew
        if hasattr(result, "json_dict") and result.json_dict:
            return GeneratedTestsReviewResult(**result.json_dict)
        
        if hasattr(result, "pydantic") and result.pydantic:
            return result.pydantic

        # Fallback se não conseguir o objeto estruturado
        return GeneratedTestsReviewResult(
            status="INVALID",
            summary="Falha ao obter resposta estruturada do revisor.",
            issues=[{
                "severity": "ERROR",
                "description": "A etapa de revisão não retornou um formato válido."
            }],
            execution_recommended=False
        )
