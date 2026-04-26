from typing import Literal

from pydantic import BaseModel, Field


ChangeSize = Literal["small", "medium", "large"]
AnalysisMode = Literal["skip", "standard", "cooperative"]
ContextLevel = Literal["none", "compact", "standard", "expanded"]


class TokenBudgetPlan(BaseModel):
    """Plano determinístico de orçamento de contexto para um arquivo."""

    file_path: str = Field(..., description="Caminho do arquivo analisado")
    change_size: ChangeSize = Field(..., description="Tamanho inferido da mudança")
    risk_hint: Literal["low", "medium", "high"] = Field(
        ..., description="Sinal determinístico inicial de risco"
    )
    analysis_mode: AnalysisMode = Field(
        ..., description="Fluxo escolhido antes de chamar LLM"
    )
    context_level: ContextLevel = Field(
        ..., description="Nível de contexto adicional permitido"
    )
    include_full_file: bool = Field(
        ..., description="Indica se o arquivo completo deve entrar no prompt"
    )
    include_memory: bool = Field(
        ..., description="Indica se a memória vetorial pode ser consultada"
    )
    max_context_chars: int = Field(
        ..., description="Limite máximo aproximado para contexto adicional"
    )
    reason: str = Field(..., description="Justificativa rastreável da decisão")
