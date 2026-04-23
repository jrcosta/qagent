from src.schemas.review_result import ReviewResult
from src.schemas.test_strategy_result import TestStrategyResult, TestCase

def _map_severity_to_priority(severity: str) -> str:
    """Mapeia a severidade de um finding para a prioridade de um caso de teste."""
    mapping = {
        "ERROR": "HIGH",
        "WARN": "MEDIUM",
        "INFO": "LOW"
    }
    return mapping.get(severity.upper(), "MEDIUM")

def build_test_strategy_from_review(file_path: str, review_result: ReviewResult) -> TestStrategyResult:
    """
    Constrói uma estratégia de testes simples baseada no resultado estruturado da revisão de código.
    Este é o primeiro passo para o handoff estruturado entre QA Agent e Test Generation.
    """
    recommended_tests = []
    
    # 1. Transformar test_needs diretos em recommended_tests
    for need in review_result.test_needs:
        recommended_tests.append(
            TestCase(
                name=need,
                test_type="UNIT",  # Assumimos UNIT por padrão na primeira versão
                priority="MEDIUM"
            )
        )
        
    # 2. Mapear findings (descobertas) para testes que previnam regressão
    for finding in review_result.findings:
        priority = _map_severity_to_priority(finding.severity)
        # Se for um erro, podemos sugerir um teste de integração, senão unitário
        test_type = "INTEGRATION" if finding.severity == "ERROR" else "UNIT"
        
        recommended_tests.append(
            TestCase(
                name=f"Prevenir regressão: {finding.description}",
                test_type=test_type,
                priority=priority
            )
        )
        
    # 3. Preencher notes com resumo
    notes = f"Estratégia gerada a partir da revisão de '{file_path}'."
    if review_result.summary:
        # Pega um trecho do resumo para não poluir muito se for longo
        summary_snippet = review_result.summary[:200]
        suffix = "..." if len(review_result.summary) > 200 else ""
        notes += f"\nResumo do QA: {summary_snippet}{suffix}"

    return TestStrategyResult(
        recommended_tests=recommended_tests,
        notes=notes
    )
