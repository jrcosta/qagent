from typing import Literal

from pydantic import BaseModel, Field


class CIFailingCheck(BaseModel):
    """Resumo de um check de CI que falhou ou foi cancelado."""

    name: str = Field(..., description="Nome do check")
    workflow: str = Field(default="", description="Nome do workflow")
    state: str = Field(default="", description="Estado bruto retornado pelo GitHub")
    bucket: str = Field(default="", description="Categoria do check no GitHub CLI")
    link: str = Field(default="", description="URL do check ou job")
    failure_excerpt: str = Field(
        default="", description="Trecho compacto dos logs de falha"
    )


class CITestExecutionResult(BaseModel):
    """Resultado da consulta aos checks de CI do PR alvo."""

    status: Literal["passed", "failed", "pending", "unavailable"] = Field(
        ..., description="Status agregado dos checks do PR"
    )
    pr_ref: str = Field(default="", description="Número, URL ou branch do PR consultado")
    summary: str = Field(..., description="Resumo legível da execução de CI")
    failing_checks: list[CIFailingCheck] = Field(default_factory=list)
