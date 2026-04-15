from crewai import Task


class QATaskFactory:
    @staticmethod
    def create(agent, file_path: str, file_diff: str, code_content: str) -> Task:
        description = f"""
Você deve investigar a mudança abaixo com postura de QA Sênior Investigador.

Arquivo alterado: {file_path}

Diff da mudança:
[INICIO_DIFF]
{file_diff}
[FIM_DIFF]

Conteúdo atual do arquivo:
[INICIO_CODIGO]
{code_content}
[FIM_CODIGO]

Instruções:
1. Primeiro, entenda exatamente o que mudou no diff.
2. Se necessário, use as tools disponíveis para buscar contexto adicional no repositório.
3. Procure arquivos relacionados, usos, testes existentes ou referências relevantes.
4. Só depois escreva a revisão final.

Sua resposta deve conter:

# Tipo da mudança
Classifique como visual, funcional, integração, validação, regra de negócio, refatoração, performance ou outro.

# Evidências observadas
Aponte os trechos ou comportamentos que justificam sua análise.

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
Só inclua se a mudança justificar.

# Pontos que precisam de esclarecimento
Liste dúvidas relevantes de negócio ou implementação.

Regras:
- não escreva resposta genérica
- não faça checklist superficial
- não diga apenas "testar funcionalidade"
- seja específico em relação ao diff e ao contexto encontrado
"""

        expected_output = """
Relatório completo em Markdown, técnico, contextualizado e baseado no diff e na investigação do repositório.
"""

        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            markdown=True,
        )