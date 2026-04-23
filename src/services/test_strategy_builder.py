from typing import Literal

from src.schemas.review_result import ReviewResult
from src.schemas.test_strategy_result import TestStrategyResult, TestCase

RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


def _map_severity_to_priority(severity: str) -> str:
    """Mapeia a severidade de um finding para a prioridade de um caso de teste."""
    mapping = {
        "ERROR": "HIGH",
        "WARN": "MEDIUM",
        "INFO": "LOW",
    }
    return mapping.get(severity.upper(), "MEDIUM")


# ---------------------------------------------------------------------------
# Políticas por nível de risco
# ---------------------------------------------------------------------------


def _build_strategy_low(
    file_path: str, review_result: ReviewResult,
) -> TestStrategyResult:
    """
    Política LOW: estratégia enxuta focada apenas em test_needs diretos.
    Findings são ignorados para manter o escopo mínimo.
    """
    recommended_tests = [
        TestCase(name=need, test_type="UNIT", priority="LOW")
        for need in review_result.test_needs
    ]

    notes = (
        f"Política LOW aplicada para '{file_path}'."
        f"\nApenas necessidades de teste diretas foram incluídas."
    )

    return TestStrategyResult(recommended_tests=recommended_tests, notes=notes)


def _build_strategy_medium(
    file_path: str, review_result: ReviewResult,
) -> TestStrategyResult:
    """
    Política MEDIUM: combina test_needs e findings com prioridade normal.
    Comportamento equivalente ao builder original.
    """
    recommended_tests = []

    for need in review_result.test_needs:
        recommended_tests.append(
            TestCase(name=need, test_type="UNIT", priority="MEDIUM")
        )

    for finding in review_result.findings:
        priority = _map_severity_to_priority(finding.severity)
        test_type = "INTEGRATION" if finding.severity == "ERROR" else "UNIT"
        recommended_tests.append(
            TestCase(
                name=f"Prevenir regressão: {finding.description}",
                test_type=test_type,
                priority=priority,
            )
        )

    notes = f"Política MEDIUM aplicada para '{file_path}'."
    if review_result.summary:
        snippet = review_result.summary[:200]
        suffix = "..." if len(review_result.summary) > 200 else ""
        notes += f"\nResumo do QA: {snippet}{suffix}"

    return TestStrategyResult(recommended_tests=recommended_tests, notes=notes)


def _build_strategy_high(
    file_path: str, review_result: ReviewResult,
) -> TestStrategyResult:
    """
    Política HIGH: estratégia detalhada priorizando cenários críticos,
    regressão e cobertura ampla. Tudo é promovido a prioridade alta.
    """
    recommended_tests = []

    # test_needs com prioridade elevada
    for need in review_result.test_needs:
        recommended_tests.append(
            TestCase(name=need, test_type="UNIT", priority="HIGH")
        )

    # findings sempre geram testes de integração em risco alto
    for finding in review_result.findings:
        recommended_tests.append(
            TestCase(
                name=f"[CRÍTICO] Prevenir regressão: {finding.description}",
                test_type="INTEGRATION",
                priority="HIGH",
            )
        )

    # Teste de regressão geral quando há achados críticos
    if any(f.severity == "ERROR" for f in review_result.findings):
        recommended_tests.append(
            TestCase(
                name=f"Teste de regressão geral para '{file_path}'",
                test_type="E2E",
                priority="HIGH",
            )
        )

    notes = (
        f"⚠️ Política HIGH aplicada para '{file_path}'."
        f"\nTodos os cenários foram priorizados como críticos."
    )
    if review_result.summary:
        snippet = review_result.summary[:200]
        suffix = "..." if len(review_result.summary) > 200 else ""
        notes += f"\nResumo do QA: {snippet}{suffix}"

    return TestStrategyResult(recommended_tests=recommended_tests, notes=notes)


# ---------------------------------------------------------------------------
# Ponto de entrada público
# ---------------------------------------------------------------------------

_POLICY_MAP = {
    "LOW": _build_strategy_low,
    "MEDIUM": _build_strategy_medium,
    "HIGH": _build_strategy_high,
}


def build_test_strategy_from_review(
    file_path: str,
    review_result: ReviewResult,
    risk_level: RiskLevel = "MEDIUM",
) -> TestStrategyResult:
    """
    Constrói uma estratégia de testes baseada no resultado da revisão,
    adaptando a política conforme o nível de risco do arquivo.

    Quando `risk_level` não é fornecido, aplica a política MEDIUM
    (comportamento equivalente à versão anterior).
    """
    policy = _POLICY_MAP.get(risk_level, _build_strategy_medium)
    return policy(file_path, review_result)

