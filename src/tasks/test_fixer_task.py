from crewai import Task


class TestFixerTaskFactory:
    @staticmethod
    def create(
        agent,
        file_path: str,
        code_content: str,
        generated_tests: str,
        review_summary: str,
        ci_execution_summary: str,
    ) -> Task:
        description = f"""
Você deve corrigir os testes gerados relacionados ao arquivo analisado: {file_path}.

Código de produção analisado:
[INICIO_CODIGO]
{code_content}
[FIM_CODIGO]

Resultado real do CI:
[INICIO_CI]
{ci_execution_summary}
[FIM_CI]

Crítica do Test Reviewer:
[INICIO_REVISAO]
{review_summary}
[FIM_REVISAO]

Testes gerados atuais:
[INICIO_TESTES_ATUAIS]
{generated_tests}
[FIM_TESTES_ATUAIS]

Sua tarefa:
1. Identifique quais testes falharam no CI e por quê.
2. Corrija expectativas especulativas para baterem com o comportamento real do código.
3. Remova ou ajuste mocks/imports incoerentes.
4. Preserve cenários úteis que já são executáveis.
5. Não altere código de produção nem proponha mudanças de contrato.

Responda APENAS com arquivos completos no formato:

### FILE: <caminho_relativo_do_arquivo_de_teste>
```
<conteúdo completo corrigido>
```

Regras:
- inclua somente arquivos de teste que precisam ser corrigidos
- não inclua explicações fora dos blocos FILE
- mantenha imports necessários
- garanta que o código seja sintaticamente válido
"""

        return Task(
            description=description,
            expected_output="Arquivos de teste corrigidos em blocos FILE.",
            agent=agent,
        )
