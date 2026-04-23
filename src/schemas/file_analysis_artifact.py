from typing import Literal, Optional
from pydantic import BaseModel, Field

from src.schemas.context_result import ContextResult
from src.schemas.review_result import ReviewResult
from src.schemas.test_strategy_result import TestStrategyResult


# ---------------------------------------------------------------------------
# Constantes de estado para orquestração
# ---------------------------------------------------------------------------

RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]
ReviewQuality = Literal["OK", "INCOMPLETE"]
TestGenerationRecommendation = Literal["RECOMMENDED", "SKIPPED"]

# Limiar mínimo de caracteres para considerar um summary aceitável
_MIN_SUMMARY_LENGTH = 20


class FileAnalysisArtifact(BaseModel):
    """
    Artefato consolidado representando o resultado completo da análise
    de um único arquivo dentro do pipeline.

    Centraliza todos os dados estruturados produzidos pelas etapas:
    Context -> QA Review -> Test Strategy

    Permite que etapas futuras consumam um único objeto em vez de
    variáveis dispersas.

    Campos de orquestração (preenchidos via `evaluate`):
    - risk_level: nível de risco inferido dos findings
    - review_quality: qualidade percebida da revisão
    - test_generation_recommendation: se a geração de testes é recomendada
    """

    file_path: str = Field(..., description="Caminho do arquivo analisado")
    context_result: Optional[ContextResult] = Field(
        None, description="Resultado da etapa de extração de contexto"
    )
    raw_review_markdown: Optional[str] = Field(
        None, description="Markdown bruto retornado pelo QA Agent"
    )
    review_result: Optional[ReviewResult] = Field(
        None, description="Resultado estruturado da revisão de código"
    )
    test_strategy_result: Optional[TestStrategyResult] = Field(
        None, description="Estratégia de testes derivada da revisão"
    )

    # --- Campos de orquestração ---
    risk_level: RiskLevel = Field(
        default="LOW", description="Nível de risco inferido da revisão"
    )
    review_quality: ReviewQuality = Field(
        default="OK", description="Qualidade percebida da revisão"
    )
    test_generation_recommendation: TestGenerationRecommendation = Field(
        default="RECOMMENDED",
        description="Recomendação sobre execução da geração de testes",
    )

    # -----------------------------------------------------------------------
    # Avaliação automática
    # -----------------------------------------------------------------------

    def evaluate(self) -> "FileAnalysisArtifact":
        """
        Preenche os campos de orquestração com base nos dados estruturados
        já presentes no artefato. Retorna `self` para permitir encadeamento.
        """
        self.risk_level = self._evaluate_risk_level()
        self.review_quality = self._evaluate_review_quality()
        self.test_generation_recommendation = (
            self._evaluate_test_generation_recommendation()
        )
        return self

    def _evaluate_risk_level(self) -> RiskLevel:
        if not self.review_result or not self.review_result.findings:
            return "LOW"

        severities = {f.severity for f in self.review_result.findings}

        if "ERROR" in severities:
            return "HIGH"
        if "WARN" in severities:
            return "MEDIUM"
        return "LOW"

    def _evaluate_review_quality(self) -> ReviewQuality:
        if not self.review_result:
            return "INCOMPLETE"

        summary = (self.review_result.summary or "").strip()
        if len(summary) < _MIN_SUMMARY_LENGTH:
            return "INCOMPLETE"

        return "OK"

    def _evaluate_test_generation_recommendation(
        self,
    ) -> TestGenerationRecommendation:
        if (
            not self.test_strategy_result
            or not self.test_strategy_result.recommended_tests
        ):
            return "SKIPPED"

        return "RECOMMENDED"
