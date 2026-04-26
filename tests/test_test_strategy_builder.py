from src.schemas.review_result import Finding, ReviewResult
from src.services.test_strategy_builder import build_test_strategy_from_review


def test_low_risk_strategy_uses_only_explicit_test_needs() -> None:
    review = ReviewResult(
        summary="Mudanca simples.",
        findings=[Finding(description="Finding informativo", severity="INFO")],
        test_needs=["Validar caso feliz"],
    )

    strategy = build_test_strategy_from_review("src/service.py", review, "LOW")

    assert [test.name for test in strategy.recommended_tests] == ["Validar caso feliz"]
    assert strategy.recommended_tests[0].priority == "LOW"
    assert strategy.recommended_tests[0].test_type == "UNIT"
    assert "Política LOW" in strategy.notes


def test_medium_risk_strategy_combines_needs_and_findings() -> None:
    review = ReviewResult(
        summary="Mudanca com comportamento parcial.",
        findings=[Finding(description="Validacao incompleta", severity="WARN")],
        test_needs=["Cobrir payload valido"],
    )

    strategy = build_test_strategy_from_review("src/service.py", review, "MEDIUM")

    assert len(strategy.recommended_tests) == 2
    assert strategy.recommended_tests[0].name == "Cobrir payload valido"
    assert strategy.recommended_tests[0].priority == "MEDIUM"
    assert strategy.recommended_tests[1].name == (
        "Prevenir regressão: Validacao incompleta"
    )
    assert strategy.recommended_tests[1].priority == "MEDIUM"


def test_high_risk_strategy_promotes_tests_and_adds_general_regression() -> None:
    review = ReviewResult(
        summary="Mudanca critica no contrato da API.",
        findings=[Finding(description="Breaking change no contrato", severity="ERROR")],
        test_needs=["Validar contrato JSON"],
    )

    strategy = build_test_strategy_from_review("src/api.py", review, "HIGH")

    assert [test.priority for test in strategy.recommended_tests] == [
        "HIGH",
        "HIGH",
        "HIGH",
    ]
    assert strategy.recommended_tests[1].test_type == "INTEGRATION"
    assert strategy.recommended_tests[2].test_type == "E2E"
    assert "Política HIGH" in strategy.notes
