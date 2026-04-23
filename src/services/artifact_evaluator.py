"""
Serviço responsável por avaliar um FileAnalysisArtifact e preencher
seus campos de orquestração (risk_level, review_quality,
test_generation_recommendation).

Separa a política de decisão da representação de dados,
permitindo que as regras evoluam independentemente do schema.
"""

from src.schemas.file_analysis_artifact import (
    FileAnalysisArtifact,
    RiskLevel,
    ReviewQuality,
    TestGenerationRecommendation,
)

# Limiar mínimo de caracteres para considerar um summary aceitável
_MIN_SUMMARY_LENGTH = 20


def evaluate_artifact(artifact: FileAnalysisArtifact) -> FileAnalysisArtifact:
    """
    Avalia o artefato e preenche os campos de orquestração com base
    nos dados estruturados já presentes. Retorna o mesmo artefato
    para permitir encadeamento.
    """
    artifact.risk_level = _evaluate_risk_level(artifact)
    artifact.review_quality = _evaluate_review_quality(artifact)
    artifact.test_generation_recommendation = (
        _evaluate_test_generation_recommendation(artifact)
    )
    return artifact


def _evaluate_risk_level(artifact: FileAnalysisArtifact) -> RiskLevel:
    """Infere o nível de risco a partir das severidades dos findings."""
    if not artifact.review_result or not artifact.review_result.findings:
        return "LOW"

    severities = {f.severity for f in artifact.review_result.findings}

    if "ERROR" in severities:
        return "HIGH"
    if "WARN" in severities:
        return "MEDIUM"
    return "LOW"


def _evaluate_review_quality(artifact: FileAnalysisArtifact) -> ReviewQuality:
    """Avalia a qualidade da revisão com base no summary."""
    if not artifact.review_result:
        return "INCOMPLETE"

    summary = (artifact.review_result.summary or "").strip()
    if len(summary) < _MIN_SUMMARY_LENGTH:
        return "INCOMPLETE"

    return "OK"


def _evaluate_test_generation_recommendation(
    artifact: FileAnalysisArtifact,
) -> TestGenerationRecommendation:
    """Decide se a geração de testes é recomendada."""
    if (
        not artifact.test_strategy_result
        or not artifact.test_strategy_result.recommended_tests
    ):
        return "SKIPPED"

    return "RECOMMENDED"
