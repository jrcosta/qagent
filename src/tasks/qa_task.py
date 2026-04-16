from crewai import Task


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

Sua resposta deve conter:

# Tipo da mudança
Classifique a mudança.

# Evidências observadas
Aponte os trechos ou comportamentos do diff, do arquivo e do contexto que sustentam sua análise.

# Impacto provável
Explique o que provavelmente foi afetado.

# Riscos identificados
Liste riscos reais e contextualizados.

# Cenários de testes manuais
Sugira cenários específicos para a mudança.

# Sugestões de testes unitários
Sugira testes unitários específicos.

# Sugestões de testes de integração
Sugira testes de integração específicos.

# Sugestões de testes de carga ou desempenho
Inclua apenas se a mudança justificar claramente.

# Pontos que precisam de esclarecimento
Liste dúvidas relevantes de negócio ou implementação.

Regras:
- não escreva resposta genérica
- não faça checklist superficial
- não diga apenas "testar funcionalidade"
- não invente contexto que não esteja no diff, no arquivo ou no contexto adicional
- não sugira performance/carga sem indício real
"""

        expected_output = """
Relatório completo em Markdown, técnico, contextualizado e baseado no diff, no conteúdo atual do arquivo e no contexto adicional do repositório.
"""

        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            markdown=True,
        )