from typing import List, Optional
from pydantic import BaseModel, Field


class ContextResult(BaseModel):
    """Schema representando o resultado da etapa de extração de contexto."""
    file_path: Optional[str] = Field(None, description="Caminho do arquivo analisado")
    summary: str = Field(..., description="Resumo do contexto")
    related_files: List[str] = Field(default_factory=list, description="Lista de arquivos relacionados")
    existing_tests: List[str] = Field(default_factory=list, description="Testes existentes encontrados no contexto")
    risks_from_context: List[str] = Field(default_factory=list, description="Riscos identificados a partir do contexto")


def parse_context_markdown_to_context_result(text: str, file_path: Optional[str] = None) -> ContextResult:
    """
    Função auxiliar simples para converter texto markdown em um ContextResult.
    Por enquanto, é um fallback seguro que encapsula o texto bruto no campo summary,
    sem tentar realizar um parsing complexo do markdown.
    """
    return ContextResult(
        file_path=file_path,
        summary=text.strip(),
        related_files=[],
        existing_tests=[],
        risks_from_context=[]
    )


def render_context_result_for_prompt(context_result: ContextResult) -> str:
    """
    Helper para converter o ContextResult estruturado no formato textual 
    esperado pelos agents.
    """
    return context_result.summary