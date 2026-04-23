from crewai import Task


class HighRiskStrategyTaskFactory:
    """Factory para criar a task de refinamento de estratégia de alto risco."""

    @staticmethod
    def create(
        agent,
        file_path: str,
        review_summary: str,
        base_strategy_text: str,
        context_summary: str = "",
    ) -> Task:
        context_block = ""
        if context_summary:
            context_block = f"""
Contexto adicional do repositório:
[INICIO_CONTEXTO]
{context_summary}
[FIM_CONTEXTO]
"""

        description = f"""
Você deve refinar a estratégia de testes abaixo para um arquivo classificado como ALTO RISCO.

Arquivo alvo: {file_path}
{context_block}
Resumo da revisão de QA:
[INICIO_REVIEW]
{review_summary}
[FIM_REVIEW]

Estratégia base já construída (NÃO descarte, apenas refine e complemente):
[INICIO_ESTRATEGIA_BASE]
{base_strategy_text}
[FIM_ESTRATEGIA_BASE]

Instruções:
1. Mantenha todos os testes já recomendados na estratégia base.
2. Adicione cenários críticos que possam estar faltando.
3. Reforce testes de regressão para comportamentos existentes.
4. Considere cenários de borda e falha.
5. Se possível, sugira testes de integração ou E2E adicionais.
6. Priorize todos os cenários adicionados como HIGH.

Sua resposta deve ser uma lista de testes adicionais no formato:
- [PRIORIDADE] (TIPO) Descrição do teste

Onde:
- PRIORIDADE: HIGH, MEDIUM ou LOW
- TIPO: UNIT, INTEGRATION ou E2E

Inclua ao final uma seção "Notas" com observações relevantes sobre a estratégia refinada.

Regras:
- não repita testes já presentes na estratégia base
- não invente contexto que não esteja na revisão ou na estratégia
- seja específico e contextualizado
"""

        expected_output = """
Lista de testes adicionais recomendados no formato especificado, seguida de notas de refinamento.
"""

        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
        )
