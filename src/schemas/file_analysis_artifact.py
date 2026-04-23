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


class FileAnalysisArtifact(BaseModel):
    """
    Artefato consolidado representando o resultado completo da análise
    de um único arquivo dentro do pipeline.

    Centraliza todos os dados estruturados produzidos pelas etapas:
    Context -> QA Review -> Test Strategy

    Permite que etapas futuras consumam um único objeto em vez de
    variáveis dispersas.

    Campos de orquestração são preenchidos externamente via
    `src.services.artifact_evaluator.evaluate_artifact`.
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

