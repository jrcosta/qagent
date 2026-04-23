"""
Runner para enriquecimento de estratégia de testes via LLM
exclusivamente para arquivos classificados como HIGH risk.

Fallback seguro: se qualquer erro ocorrer, retorna a estratégia
base inalterada.
"""

import re

from crewai import Crew, Process

from src.agent.high_risk_strategy_agent import HighRiskStrategyAgentFactory
from src.config.settings import Settings
from src.schemas.context_result import ContextResult, render_context_result_for_prompt
from src.schemas.review_result import ReviewResult
from src.schemas.test_strategy_result import (
    TestCase,
    TestStrategyResult,
    render_test_strategy_result_for_prompt,
)
from src.tasks.high_risk_strategy_task import HighRiskStrategyTaskFactory


class HighRiskTestStrategyRunner:
    """
    Executa um agente LLM especializado para refinar a estratégia de testes
    em arquivos de alto risco.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(
        self,
        file_path: str,
        review_result: ReviewResult,
        base_strategy: TestStrategyResult,
        context_result: ContextResult | None = None,
    ) -> TestStrategyResult:
        """
        Enriquece a estratégia base via LLM. Em caso de falha,
        retorna a estratégia base sem modificações.
        """
        try:
            return self._run_crew(
                file_path=file_path,
                review_result=review_result,
                base_strategy=base_strategy,
                context_result=context_result,
            )
        except Exception as exc:
            print(f"  ⚠️ Fallback: enriquecimento HIGH risk falhou para {file_path}: {exc}")
            return base_strategy

    def _run_crew(
        self,
        file_path: str,
        review_result: ReviewResult,
        base_strategy: TestStrategyResult,
        context_result: ContextResult | None,
    ) -> TestStrategyResult:
        base_strategy_text = render_test_strategy_result_for_prompt(base_strategy)

        context_summary = ""
        if context_result:
            context_summary = render_context_result_for_prompt(context_result)

        review_summary = review_result.summary or ""

        agent = HighRiskStrategyAgentFactory(self.settings).create()
        task = HighRiskStrategyTaskFactory.create(
            agent=agent,
            file_path=file_path,
            review_summary=review_summary,
            base_strategy_text=base_strategy_text,
            context_summary=context_summary,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )

        result = crew.kickoff()

        raw_output = ""
        if hasattr(result, "tasks_output") and result.tasks_output:
            task_output = result.tasks_output[-1]
            if hasattr(task_output, "raw") and task_output.raw:
                raw_output = task_output.raw
        if not raw_output and hasattr(result, "raw") and result.raw:
            raw_output = result.raw
        if not raw_output:
            raw_output = str(result)

        return self._merge_strategy(base_strategy, raw_output)

    def _merge_strategy(
        self, base: TestStrategyResult, llm_output: str
    ) -> TestStrategyResult:
        """
        Mescla a estratégia base com os testes adicionais sugeridos pelo LLM.
        Preserva todos os testes originais e apenas adiciona novos.
        """
        additional_tests = self._parse_additional_tests(llm_output)
        additional_notes = self._parse_additional_notes(llm_output)

        merged_tests = list(base.recommended_tests) + additional_tests

        merged_notes = base.notes
        if additional_notes:
            merged_notes += f"\n\n--- Refinamento HIGH risk (via LLM) ---\n{additional_notes}"

        if additional_tests:
            print(f"  🔬 {len(additional_tests)} teste(s) adicionais sugeridos pelo agente HIGH risk")

        return TestStrategyResult(
            recommended_tests=merged_tests,
            notes=merged_notes,
        )

    @staticmethod
    def _parse_additional_tests(text: str) -> list[TestCase]:
        """
        Extrai testes adicionais do output do LLM no formato:
        - [PRIORIDADE] (TIPO) Descrição
        """
        tests: list[TestCase] = []
        pattern = re.compile(
            r"^[-*]\s*\[(\w+)\]\s*\((\w+)\)\s*(.+)$", re.MULTILINE
        )

        for match in pattern.finditer(text):
            raw_priority = match.group(1).upper()
            raw_type = match.group(2).upper()
            description = match.group(3).strip()

            priority = raw_priority if raw_priority in ("LOW", "MEDIUM", "HIGH") else "HIGH"
            test_type = raw_type if raw_type in ("UNIT", "INTEGRATION", "E2E") else "UNIT"

            tests.append(
                TestCase(
                    name=description,
                    test_type=test_type,
                    priority=priority,
                )
            )

        return tests

    @staticmethod
    def _parse_additional_notes(text: str) -> str:
        """Extrai a seção de Notas do output do LLM, se presente."""
        # Procura por um heading "Notas" ou "Notes"
        match = re.search(
            r"(?:^|\n)#+\s*[Nn]otas?\s*\n(.*)", text, re.DOTALL
        )
        if match:
            return match.group(1).strip()

        # Fallback: procura por "Notas:" inline
        match = re.search(
            r"(?:^|\n)[Nn]otas?:\s*(.*)", text, re.DOTALL
        )
        if match:
            return match.group(1).strip()

        return ""
