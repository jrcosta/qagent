from crewai import Task
from src.schemas.generated_test_review_result import GeneratedTestsReviewResult


class TestReviewerTaskFactory:
    @staticmethod
    def create(
        agent,
        file_path: str,
        code_content: str,
        qa_report: str,
        test_strategy: str,
        generated_tests: str,
        file_diff: str = "",
    ) -> Task:
        diff_block = ""
        if file_diff:
            diff_block = f"""
DIFF ANALISADO (Mudanças que motivaram os testes):
[INICIO_DIFF]
{file_diff}
[FIM_DIFF]
"""

        description = f"""
Você deve revisar criticamente os testes unitários que foram gerados para o arquivo: {file_path}.

CONTEXTO ORIGINAL (Arquivo Completo):
[INICIO_CODIGO_ORIGINAL]
{code_content}
[FIM_CODIGO_ORIGINAL]

{diff_block}

RELATÓRIO DE QA E RISCOS:
[INICIO_RELATORIO]
{qa_report}
[FIM_RELATORIO]

ESTRATÉGIA DE TESTES DEFINIDA:
[INICIO_ESTRATEGIA]
{test_strategy}
[FIM_ESTRATEGIA]

TESTES GERADOS PARA REVISÃO:
[INICIO_TESTES_GERADOS]
{generated_tests}
[FIM_TESTES_GERADOS]

SUA TAREFA:
1. Avalie se os testes cobrem os riscos reais apontados no relatório de QA e as mudanças mostradas no DIFF.
2. Verifique se os testes usam nomes de métodos/classes que realmente existem no código original.
3. Identifique se há testes genéricos demais (ex: apenas testa se não lança exceção sem validar o retorno).
4. Procure por imports quebrados ou mocks incoerentes.
5. Verifique se a estratégia de testes foi seguida (ex: se pediu testes de borda, eles existem?).
6. Identifique cenários críticos ausentes.

CRITÉRIOS DE STATUS:
- APPROVED: Testes estão corretos, coerentes e cobrem os riscos.
- NEEDS_CHANGES: Testes têm valor mas precisam de ajustes técnicos ou melhor cobertura de cenários.
- INVALID: Testes estão completamente errados, incoerentes ou usam código inexistente.

Sua resposta deve ser estruturada conforme o schema GeneratedTestsReviewResult.
"""

        expected_output = """
Um objeto estruturado contendo o status da revisão, resumo dos achados, lista de problemas identificados, 
cenários ausentes e recomendações de correção ou execução.
"""

        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            output_json=GeneratedTestsReviewResult,
        )
