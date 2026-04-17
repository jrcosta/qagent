
from __future__ import annotations

from crewai import Task


class QATaskFactory:
    @staticmethod
    def create(
        agent,
        file_path: str,
        file_diff: str,
        code_content: str,
        repo_context: str,
        change_hints: str,
        all_changed_files: list[str] | None = None,
        debug_logger=None,
    ) -> Task:
        changed_files_block = "\n".join(all_changed_files or [])

        description = f"""
Analise criticamente a mudança do arquivo abaixo.

Arquivo analisado:
{file_path}

Outros arquivos alterados nesta execução:
{changed_files_block or "Nenhum adicional informado."}

Diff:
```diff
{file_diff}
```

Conteúdo atual do arquivo:
```text
{code_content}
```

Contexto inicial do repositório:
{repo_context}

Pistas gerais da mudança:
{change_hints}

Instruções:
- Não se limite a resumir a mudança.
- Primeiro tente entender a intenção aparente da alteração.
- Depois tente identificar inconsistências, fragilidades, regressões ou lacunas de cobertura.
- Se o diff não for suficiente, use as tools disponíveis para investigar arquivos relacionados, testes, stack do repositório e documentação oficial.
- Não assuma framework, arquitetura ou domínio específico sem evidência.
- Evite riscos genéricos sem base observável.
- Quando algo depender do comportamento da linguagem, framework ou ferramenta, identifique a stack e use documentação oficial como apoio.

Formato obrigatório da resposta:

# Arquivo analisado: {file_path}

# Intenção aparente da mudança
- ...

# Defeitos concretos ou suspeitas fortes
- Suspeita:
- Evidência:
- Impacto provável:
- Como validar:

# Riscos identificados
- ...

# Cenários de testes manuais
- ...

# Sugestões de testes automatizados
- ...

# Pontos que precisam de esclarecimento
- ...
"""

        if debug_logger:
            debug_logger.write_text("task_prompt.md", description)

        return Task(
            description=description,
            expected_output="Relatório técnico em markdown, com evidências concretas e sugestões de validação.",
            agent=agent,
        )
