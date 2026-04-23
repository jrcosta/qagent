import re
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


# ---------------------------------------------------------------------------
# Seções conhecidas do markdown produzido pelo QA Agent
# ---------------------------------------------------------------------------

# Seções cujo conteúdo deve alimentar findings
_FINDING_SECTIONS = [
    "riscos identificados",
    "evidências observadas",
    "impacto provável",
    "pontos que precisam de esclarecimento",
]

# Seções cujo conteúdo deve alimentar test_needs
_TEST_SECTIONS = [
    "cenários de testes manuais",
    "sugestões de testes unitários",
    "sugestões de testes de integração",
    "sugestões de testes de carga ou desempenho",
]

# Seções usadas para compor o summary
_SUMMARY_SECTIONS = [
    "tipo da mudança",
    "impacto provável",
]

# Palavras‑chave usadas para inferir severidade de um finding
_SEVERITY_KEYWORDS: dict[str, list[str]] = {
    "ERROR": [
        "crítico", "crítica", "alto risco", "grave", "erro", "breaking",
        "falha", "vulnerabilidade",
    ],
    "WARN": [
        "atenção", "médio risco", "warning", "cuidado", "parcial",
        "incompleto", "incompleta",
    ],
    # Qualquer coisa que não case com ERROR/WARN será INFO (default)
}

# Regex para capturar seções em headings de nível 1 ou 2
_SECTION_RE = re.compile(r"^#{1,2}\s+(.+)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _extract_sections(text: str) -> dict[str, str]:
    """
    Divide o markdown em um dicionário {título_normalizado: conteúdo}.
    As chaves são lower‑case e sem espaços extras.
    """
    matches = list(_SECTION_RE.finditer(text))

    if not matches:
        return {}

    sections: dict[str, str] = {}

    for i, match in enumerate(matches):
        title = match.group(1).strip().lower()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[title] = text[start:end].strip()

    return sections


def _extract_bullets(block: str) -> list[str]:
    """
    Extrai itens de listas markdown (-, *, 1.) de um bloco de texto.
    Retorna strings limpas, sem o marcador.
    """
    items: list[str] = []

    for line in block.splitlines():
        stripped = line.strip()
        # Bullet: - item  ou  * item
        if stripped.startswith(("- ", "* ")):
            items.append(stripped[2:].strip())
        # Lista numerada: 1. item
        elif re.match(r"^\d+\.\s", stripped):
            items.append(re.sub(r"^\d+\.\s*", "", stripped).strip())

    return [item for item in items if item]


def _infer_severity(text: str) -> Literal["INFO", "WARN", "ERROR"]:
    """
    Infere a severidade de um finding a partir de palavras‑chave no texto.
    Retorna ERROR, WARN ou INFO (conservador por padrão).
    """
    lower = text.lower()

    for severity, keywords in _SEVERITY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return severity  # type: ignore[return-value]

    return "INFO"


def _parse_findings(sections: dict[str, str]) -> list[Finding]:
    """Extrai Findings das seções relevantes do markdown."""
    findings: list[Finding] = []

    for section_name in _FINDING_SECTIONS:
        block = sections.get(section_name, "")
        if not block:
            continue

        bullets = _extract_bullets(block)

        if bullets:
            for bullet in bullets:
                findings.append(Finding(
                    description=bullet,
                    severity=_infer_severity(bullet),
                    line_number=None,
                ))
        else:
            # Seção existe mas sem bullets — trata o bloco inteiro como um finding
            cleaned = block.strip()
            if cleaned:
                findings.append(Finding(
                    description=cleaned,
                    severity=_infer_severity(cleaned),
                    line_number=None,
                ))

    return findings


def _parse_test_needs(sections: dict[str, str]) -> list[str]:
    """Extrai necessidades de teste das seções relevantes do markdown."""
    needs: list[str] = []

    for section_name in _TEST_SECTIONS:
        block = sections.get(section_name, "")
        if not block:
            continue

        bullets = _extract_bullets(block)

        if bullets:
            needs.extend(bullets)
        else:
            cleaned = block.strip()
            if cleaned:
                needs.append(cleaned)

    return needs


def _build_summary(sections: dict[str, str], raw_text: str) -> str:
    """
    Monta o summary a partir das seções de resumo quando disponíveis,
    ou usa o texto bruto completo como fallback.
    """
    parts: list[str] = []

    for section_name in _SUMMARY_SECTIONS:
        block = sections.get(section_name, "")
        if block:
            parts.append(block.strip())

    if parts:
        return "\n\n".join(parts)

    # Fallback: texto bruto (comportamento anterior)
    return raw_text.strip()


# ---------------------------------------------------------------------------
# Função pública — ponto de entrada do parser
# ---------------------------------------------------------------------------

def parse_review_markdown_to_review_result(text: str) -> ReviewResult:
    """
    Converte o markdown gerado pelo QA Agent em um ReviewResult estruturado.

    Estratégia:
    1. Tenta dividir o texto em seções conhecidas.
    2. Extrai findings, test_needs e summary das seções relevantes.
    3. Se não encontrar seções, faz fallback seguro preenchendo apenas o summary
       com o texto bruto (comportamento anterior preservado).
    """
    sections = _extract_sections(text)

    # Se não conseguimos extrair seções, fallback completo
    if not sections:
        return ReviewResult(
            summary=text.strip(),
            findings=[],
            test_needs=[],
        )

    summary = _build_summary(sections, text)
    findings = _parse_findings(sections)
    test_needs = _parse_test_needs(sections)

    return ReviewResult(
        summary=summary,
        findings=findings,
        test_needs=test_needs,
    )