from __future__ import annotations

from typing import Optional

from crewai import Task

try:
    from src.utils.debug_logger import DebugLogger
except Exception:  # pragma: no cover
    DebugLogger = None  # type: ignore


class QATaskFactory:
    @staticmethod
    def create(
        agent,
        file_path: str,
        file_diff: str,
        code_content: str,
        repo_context: str,
        change_hints: str = "",
        all_changed_files: Optional[list[str]] = None,
        debug_logger: Optional[DebugLogger] = None,
    ) -> Task:
        changed_files_block = "\n".join(all_changed_files or []) or "Nenhum outro arquivo informado."

        description = f"""
Você deve revisar a mudança abaixo com postura de QA Sênior Investigador, de forma agnóstica à linguagem e ao framework.

Arquivo alterado: {file_path}

Todos os arquivos alterados nesta execução:
[INICIO_ARQUIVOS_ALTERADOS]
{changed_files_block}
[FIM_ARQUIVOS_ALTERADOS]

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

Pistas de revisão:
[INICIO_PISTAS]
{change_hints or 'Sem pistas adicionais.'}
[FIM_PISTAS]

Instruções:
1. Entenda a intenção aparente da mudança a partir do diff e do código atual.
2. Tente identificar inconsistências entre a intenção aparente da alteração e o que o código realmente faz.
3. Não assuma domínio específico. Analise a partir de coerência, contrato, integração, cobertura e risco de regressão.
4. Use tools quando o diff não for suficiente. Em especial, você pode:
   - inspecionar a stack do repositório,
   - localizar documentação oficial da tecnologia detectada,
   - ler arquivos relacionados,
   - buscar usos de símbolos ou módulos,
   - localizar testes relacionados.
5. Ao usar tools, incorpore explicitamente o que foi encontrado à análise.
6. Priorize defeitos concretos ou suspeitas fortes sustentadas por evidência. Evite riscos genéricos sem base observável.
7. Quando não houver evidência suficiente, declare a limitação com honestidade.
8. Se houver múltiplos arquivos alterados, correlacione-os quando isso ajudar a explicar um risco ou uma lacuna de cobertura.

Sua resposta deve conter:

# Tipo da mudança
Classifique a mudança.

# Intenção aparente da mudança
Explique o que a alteração parece querer fazer.

# Defeitos concretos ou suspeitas fortes
Liste defeitos concretos ou suspeitas fortes sustentadas por evidência.
Para cada item, informe:
- Suspeita
- Evidência
- Por que isso pode estar errado ou frágil
- Como validar ou reproduzir
- Nível de confiança

# Evidências observadas
Aponte os trechos do diff, do arquivo, do contexto e das tools que sustentam sua análise.

# Impacto provável
Explique o que provavelmente foi afetado.

# Riscos identificados
Liste apenas riscos contextualizados e sustentados por evidência.

# Cenários de testes manuais
Sugira cenários específicos para a mudança.

# Sugestões de testes unitários
Sugira testes unitários específicos.

# Sugestões de testes de integração
Sugira testes de integração específicos.

# Sugestões de testes de carga ou desempenho
Inclua apenas se a mudança justificar claramente.

# Pontos que precisam de esclarecimento
Liste dúvidas relevantes de implementação, contrato ou comportamento.

Regras:
- não escreva resposta genérica
- não faça checklist superficial
- não diga apenas "testar funcionalidade"
- não invente contexto que não esteja no diff, no arquivo, no contexto ou nas tools
- não sugira performance/carga sem indício real
- não assuma tecnologias específicas sem evidência
- use documentação oficial apenas quando ela realmente ajudar a interpretar a mudança
"""

        expected_output = (
            "Relatório completo em Markdown, técnico, investigativo, agnóstico à stack e baseado em evidências "
            "do diff, do código atual, do contexto do repositório e das tools utilizadas."
        )

        if debug_logger:
            debug_logger.write_text("task_prompt.md", description)

        return Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            markdown=True,
        )
