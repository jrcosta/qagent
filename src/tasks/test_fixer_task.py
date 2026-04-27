from crewai import Task

class TestFixerTaskFactory:
    @staticmethod
    def create(
        agent,
        file_path: str,
        code_content: str,
        test_strategy: str,
        failed_tests: str,
        review_report: str,
    ) -> Task:
        description = f"""
Você deve corrigir os testes unitários que falharam na revisão crítica para o arquivo: {file_path}.

CÓDIGO FONTE ORIGINAL:
[INICIO_CODIGO_ORIGINAL]
{code_content}
[FIM_CODIGO_ORIGINAL]

ESTRATÉGIA DE TESTES:
[INICIO_ESTRATEGIA]
{test_strategy}
[FIM_ESTRATEGIA]

TESTES QUE PRECISAM DE CORREÇÃO:
[INICIO_TESTES_FALHOS]
{failed_tests}
[FIM_TESTES_FALHOS]

RELATÓRIO DE REVISÃO CRÍTICA (Problemas a corrigir):
[INICIO_REVISAO]
{review_report}
[FIM_REVISAO]

SUA TAREFA:
1. Analise cada problema apontado no relatório de revisão.
2. Corrija a lógica, imports, mocks ou assertions nos testes falhos.
3. Se o relatório indicar cenários ausentes, implemente-os.
4. Garanta que o código resultante seja completo e executável.
5. Siga rigorosamente as convenções de código do arquivo original.

Sua resposta deve ser APENAS no formato abaixo:

### FILE: <caminho_relativo_do_arquivo_de_teste>
```
<código completo e corrigido do arquivo de teste>
```

NÃO inclua explicações fora dos blocos de código.
"""
        expected_output = "O código completo e corrigido dos arquivos de teste, pronto para execução."

        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
        )
