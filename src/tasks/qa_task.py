from crewai import Task

from src.schemas.review_result import ReviewResult


class QATaskFactory:
    @staticmethod
    def create(
        agent,
        file_path: str,
        file_diff: str,
        code_content: str,
        repo_context: str,
    ) -> Task:
        description = f"""
Você deve revisar a mudança abaixo com postura de QA Sênior Investigador.

Arquivo alterado: {file_path}

Diff da mudança:
[INICIO_DIFF]
{file_diff}
[FIM_DIFF]

Conteúdo atual do arquivo:
[INICIO_CODIGO]
{code_content}
[FIM_CODIGO]

Contexto adicional do repositório:
[INICIO_CONTEXTO]
{repo_context}
[FIM_CONTEXTO]

Instruções:
1. Entenda exatamente o que mudou no diff.
2. Use o conteúdo atual do arquivo para interpretar a mudança com precisão.
3. Use o contexto adicional do repositório para reduzir respostas genéricas.
4. Não invente regra de negócio sem evidência.
5. Seja específico sobre o comportamento alterado e impacto provável.

Sua resposta deve preencher o contrato ReviewResult:
- summary: resumo objetivo do tipo de mudança e impacto provável
- findings: riscos reais, cada um com description, severity (INFO, WARN ou ERROR)
  e line_number quando houver uma linha verificável
- test_needs: cenários específicos que precisam ser cobertos por testes

Regras:
- não escreva resposta genérica
- não faça checklist superficial
- não diga apenas "testar funcionalidade"
- não invente contexto que não esteja no diff, no arquivo ou no contexto adicional
- não sugira performance/carga sem indício real
"""

        expected_output = (
            "Objeto ReviewResult válido, técnico e fundamentado no diff, "
            "sem campos adicionais."
        )

        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            output_pydantic=ReviewResult,
        )
