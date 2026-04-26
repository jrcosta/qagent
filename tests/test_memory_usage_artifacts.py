import unittest

from src.crew.test_generator_crew import (
    _memory_limit_for_risk,
    _parse_memory_result,
    render_compact_generation_report,
)
from src.schemas.review_result import Finding, ReviewResult
from src.schemas.test_strategy_result import TestCase as StrategyTestCase
from src.schemas.test_strategy_result import TestStrategyResult as StrategyResult


class MemoryUsageArtifactTests(unittest.TestCase):
    def test_parse_memory_result_extracts_structured_lessons(self):
        raw = (
            "[distance=0.421] (PR #63 em jrcosta/repo_alvo_api_simples, por qagent[bot])\n"
            "  Lição: Validar campos novos no contrato JSON.\n\n"
            "[distance=0.812] (PR #61 em jrcosta/repo_alvo_api_simples, por reviewer)\n"
            "  Lição: Cobrir compatibilidade de clientes antigos."
        )

        memories = _parse_memory_result(raw)

        self.assertEqual(2, len(memories))
        self.assertEqual(63, memories[0]["pr_number"])
        self.assertEqual("jrcosta/repo_alvo_api_simples", memories[0]["repo"])
        self.assertEqual("qagent[bot]", memories[0]["author"])
        self.assertEqual(0.421, memories[0]["distance"])
        self.assertEqual("Validar campos novos no contrato JSON.", memories[0]["lesson"])

    def test_parse_memory_result_ignores_empty_or_missing_memory_messages(self):
        self.assertEqual([], _parse_memory_result(""))
        self.assertEqual([], _parse_memory_result("Nenhuma memória relevante encontrada para esta consulta."))

    def test_memory_limit_is_adaptive_by_risk(self):
        self.assertEqual(2, _memory_limit_for_risk("LOW"))
        self.assertEqual(3, _memory_limit_for_risk("MEDIUM"))
        self.assertEqual(5, _memory_limit_for_risk("HIGH"))

    def test_compact_generation_report_uses_structured_review_and_strategy(self):
        report = render_compact_generation_report(
            review_result=ReviewResult(
                summary="Mudança em validação de usuário.",
                findings=[
                    Finding(
                        description="Validar campo vip com tipo incorreto",
                        severity="WARN",
                    )
                ],
                test_needs=["Cobrir valor default falso"],
            ),
            test_strategy=StrategyResult(
                recommended_tests=[
                    StrategyTestCase(
                        name="validar default false",
                        test_type="UNIT",
                        priority="HIGH",
                    )
                ]
            ),
        )

        self.assertIn("WARN: Validar campo vip", report)
        self.assertIn("Cobrir valor default falso", report)
        self.assertIn("UNIT HIGH: validar default false", report)


if __name__ == "__main__":
    unittest.main()
