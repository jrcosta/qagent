from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class GeneratedTestIssue(BaseModel):
    """
    Schema representando um problema ou ponto de atenção identificado
    durante a revisão crítica dos testes gerados.
    """
    severity: Literal["INFO", "WARN", "ERROR"] = Field(
        ..., description="Severidade do problema identificado"
    )
    description: str = Field(..., description="Descrição detalhada do problema")
    related_test: Optional[str] = Field(
        None, description="Nome ou referência ao teste relacionado, se aplicável"
    )
    suggested_fix: Optional[str] = Field(
        None, description="Sugestão de correção para o problema"
    )


class GeneratedTestsReviewResult(BaseModel):
    """
    Schema representando o resultado final da revisão crítica
    dos testes gerados pelo Test Generator.
    """
    status: Literal["APPROVED", "NEEDS_CHANGES", "INVALID"] = Field(
        ..., description="Status final da revisão"
    )
    summary: str = Field(..., description="Resumo executivo da revisão")
    issues: List[GeneratedTestIssue] = Field(
        default_factory=list, description="Lista de problemas identificados"
    )
    missing_scenarios: List[str] = Field(
        default_factory=list, description="Cenários importantes que não foram cobertos"
    )
    execution_recommended: bool = Field(
        default=False, description="Indica se é recomendado executar esses testes automaticamente"
    )
    execution_reason: Optional[str] = Field(
        None, description="Justificativa para a recomendação de execução (ou não)"
    )
    suggested_fixes: List[str] = Field(
        default_factory=list, description="Lista de correções sugeridas de alto nível"
    )
