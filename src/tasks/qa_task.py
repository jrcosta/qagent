from crewai import Task


class QATaskFactory:
    @staticmethod
    def create(agent, file_path: str, code_content: str) -> Task:
        description = f"""
Você é um QA Sênior e deve produzir um relatório técnico completo sobre a mudança abaixo.

Arquivo: {file_path}

Conteúdo do arquivo:
[INICIO_CODIGO]
{code_content}
[FIM_CODIGO]

Analise com foco em:
- riscos funcionais
- regressão
- comportamento inválido
- casos de borda
- integração
- observabilidade
- impacto em performance, quando aplicável

Preencha obrigatoriamente estas seções:
# Resumo da mudança
# Riscos identificados
# Cenários de testes manuais
# Sugestões de testes unitários
# Sugestões de testes de integração
# Sugestões de testes de carga ou desempenho
# Pontos que precisam de esclarecimento

Regras obrigatórias:
- não inclua "Thought:"
- não inclua raciocínio interno
- não inclua observações sobre como você pensou
- não faça conclusão final
- não diga "o relatório acima"
- não resuma a resposta em um único parágrafo
- entregue apenas o relatório final em markdown
"""

        expected_output = """
Relatório completo em Markdown, com todas as seções solicitadas preenchidas.
"""

        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            markdown=True,
            output_file="outputs/analysis.md",
        )