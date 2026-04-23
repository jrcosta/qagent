from typing import Dict, List, Literal, Optional
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

    # --- Campos de observabilidade ---
    executed_steps: List[str] = Field(
        default_factory=list, description="Etapas executadas com sucesso"
    )
    skipped_steps: List[str] = Field(
        default_factory=list, description="Etapas que foram puladas"
    )
    applied_policies: List[str] = Field(
        default_factory=list, description="Políticas aplicadas durante o pipeline"
    )
    fallbacks_triggered: List[str] = Field(
        default_factory=list, description="Fallbacks acionados durante o pipeline"
    )
    step_durations_ms: Dict[str, float] = Field(
        default_factory=dict, description="Duração de cada etapa em milissegundos"
    )
    diagnostic_notes: List[str] = Field(
        default_factory=list, description="Notas de diagnóstico registradas pelo pipeline"
    )

    # --- Helpers de observabilidade ---

    def mark_step_executed(self, step: str) -> None:
        """Registra uma etapa como executada."""
        self.executed_steps.append(step)

    def mark_step_skipped(self, step: str, reason: str = "") -> None:
        """Registra uma etapa como pulada, com motivo opcional."""
        entry = f"{step}: {reason}" if reason else step
        self.skipped_steps.append(entry)

    def add_policy(self, policy: str) -> None:
        """Registra uma política aplicada."""
        self.applied_policies.append(policy)

    def add_fallback(self, fallback: str) -> None:
        """Registra um fallback acionado."""
        self.fallbacks_triggered.append(fallback)

    def add_note(self, note: str) -> None:
        """Adiciona uma nota de diagnóstico."""
        self.diagnostic_notes.append(note)

    def record_duration(self, step: str, duration_ms: float) -> None:
        """Registra a duração de uma etapa em milissegundos."""
        self.step_durations_ms[step] = round(duration_ms, 2)


