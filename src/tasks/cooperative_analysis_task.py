from crewai import Task


class CooperativeAnalysisTaskFactory:
    """Task principal para análise coordenada por gerente multiagente."""

    @staticmethod
    def create(
        file_path: str,
        file_diff: str,
        code_content: str,
        repo_context: str,
    ) -> Task:
        description = f"""
Você deve coordenar uma análise multiagente de QA para o arquivo abaixo.

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

Como gerente coordenador:
1. Delegue a análise de riscos para o especialista de QA.
2. Delegue a estratégia de testes para o especialista de estratégia.
3. Peça uma crítica final do raciocínio para reduzir achados genéricos ou inventados.
4. Consolide uma resposta final única em Markdown.
5. Não substitua validações determinísticas do pipeline; produza uma análise de entrada melhor.

Sua resposta final deve conter exatamente estas seções:

# Tipo da mudança
Classifique a mudança.

# Evidências observadas
Aponte trechos ou comportamentos do diff, do arquivo e do contexto que sustentam a análise.

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

# Validação cooperativa
Explique brevemente como as conclusões foram revisadas pelos especialistas.

Regras:
- não invente regra de negócio sem evidência
- não produza checklist superficial
- não diga apenas "testar funcionalidade"
- não sugira performance/carga sem indício real
- preserve o formato das seções para que o parser estruturado continue funcionando
"""

        expected_output = """
Relatório final em Markdown, coordenado por gerente multiagente, com as seções exigidas e conclusões baseadas no diff, no código e no contexto do repositório.
"""

        return Task(
            description=description,
            expected_output=expected_output,
            markdown=True,
        )
