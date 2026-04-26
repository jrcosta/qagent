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
        ci_execution_summary: str = "",
    ) -> Task:
        diff_block = ""
        if file_diff:
            diff_block = f"""
DIFF ANALISADO (Mudanças que motivaram os testes):
[INICIO_DIFF]
{file_diff}
[FIM_DIFF]
"""

        ci_block = ""
        if ci_execution_summary:
            ci_block = f"""
RESULTADO REAL DO CI DO PR COM OS TESTES GERADOS:
[INICIO_CI]
{ci_execution_summary}
[FIM_CI]
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

{ci_block}

SUA TAREFA:
1. Use primeiro o resultado real do CI, quando fornecido, como evidência principal para a crítica.
2. Se o CI falhou, relacione as falhas aos testes gerados e explique se o problema é teste incorreto, expectativa especulativa, import quebrado, mock incoerente ou contrato real não implementado.
3. Avalie se os testes cobrem os riscos reais apontados no relatório de QA e as mudanças mostradas no DIFF.
4. Verifique se os testes usam nomes de métodos/classes que realmente existem no código original.
5. Identifique se há testes genéricos demais (ex: apenas testa se não lança exceção sem validar o retorno).
6. Procure por imports quebrados ou mocks incoerentes.
7. Verifique se a estratégia de testes foi seguida (ex: se pediu testes de borda, eles existem?).
8. Identifique cenários críticos ausentes.

CRITÉRIOS DE STATUS:
- APPROVED: Testes estão corretos, coerentes e cobrem os riscos. Use este status somente quando `issues`, `missing_scenarios` e `suggested_fixes` estiverem vazios.
- NEEDS_CHANGES: Testes têm valor mas precisam de ajustes técnicos, melhor cobertura de cenários ou possuem qualquer problema WARN/INFO acionável.
- INVALID: Testes estão completamente errados, incoerentes, usam código inexistente ou possuem qualquer problema ERROR.

REGRA DE CONSISTÊNCIA:
- Nunca retorne APPROVED se você apontou problemas, cenários ausentes ou correções recomendadas.
- Se houver qualquer issue com severity ERROR, o status deve ser INVALID.
- Se houver qualquer issue WARN/INFO, cenário ausente ou correção recomendada, o status deve ser NEEDS_CHANGES.
- Se o CI reportou falhas causadas pelos testes gerados, não retorne APPROVED.

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
