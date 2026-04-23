from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class Finding(BaseModel):
    """Schema representando uma descoberta isolada feita durante a revisão de código."""
    description: str = Field(..., description="Descrição da descoberta")
    severity: Literal["INFO", "WARN", "ERROR"] = Field(
        default="INFO",
        description="Severidade da descoberta"
    )
    line_number: Optional[int] = Field(None, description="Número da linha onde a descoberta ocorreu, se aplicável")


class ReviewResult(BaseModel):
    """Schema representando o resultado da etapa de revisão de código."""
    summary: str = Field(..., description="Resumo geral da revisão")
    findings: List[Finding] = Field(default_factory=list, description="Lista de descobertas identificadas")
    test_needs: List[str] = Field(default_factory=list, description="Necessidades de testes identificadas")


def parse_review_markdown_to_review_result(text: str) -> ReviewResult:
    """
    Função auxiliar simples para converter texto markdown em um ReviewResult.
    Atualmente retorna um fallback preenchendo o texto bruto no summary.
    """
    return ReviewResult(
        summary=text.strip(),
        findings=[],
        test_needs=[]
    )