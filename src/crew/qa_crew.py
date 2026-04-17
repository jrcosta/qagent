from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from crewai import Crew, Process

from src.agent.qa_agent import QAAgentFactory
from src.config.settings import Settings
from src.services.context_builder import RepoContextBuilder
from src.tasks.qa_task import QATaskFactory

try:
    from src.utils.debug_logger import DebugLogger
except Exception:  # pragma: no cover
    DebugLogger = None  # type: ignore


class QACrewRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _build_change_hints(self, file_path: str, file_diff: str, code_content: str) -> str:
        hints: list[str] = []

        added_lines = len(re.findall(r"^\+(?!\+\+)", file_diff, flags=re.MULTILINE))
        removed_lines = len(re.findall(r"^\-(?!--)", file_diff, flags=re.MULTILINE))
        modified_existing_behavior = added_lines > 0 and removed_lines > 0

        if modified_existing_behavior:
            hints.append(
                "A mudança altera comportamento existente. Verifique se a substituição parece completa e coerente com o restante do código."
            )
        elif added_lines:
            hints.append(
                "A mudança introduz código novo. Verifique se a nova lógica está integrada de forma coerente com estruturas, contratos e convenções já existentes."
            )
        elif removed_lines:
            hints.append(
                "A mudança remove código existente. Verifique se a remoção elimina proteção, cobertura, validação, tratamento de erro ou comportamento ainda necessário."
            )

        if re.search(r"^-.*def test_|^-.*class Test|^-.*@pytest|^-.*assert ", file_diff, flags=re.MULTILINE):
            hints.append(
                "Há redução aparente de cobertura automatizada. Investigue se a mudança remove proteção útil ou diminui a capacidade de detectar regressões."
            )

        if re.search(r"^\+.*(def |class |function |interface |type )", file_diff, flags=re.MULTILINE):
            hints.append(
                "Há definição nova ou alterada de unidade lógica. Verifique se nome, responsabilidade, uso e comportamento aparente estão alinhados."
            )

        if re.search(r"\b(import|from .* import|require\(|using |include )", code_content):
            hints.append(
                "Considere dependências e integrações aparentes. Verifique se a mudança preserva compatibilidade com módulos, serviços, contratos, interfaces ou componentes relacionados."
            )

        if re.search(r"\b(try:|except |catch\s*\(|raise |throw |assert )", code_content):
            hints.append(
                "Observe tratamento de erro e mecanismos de proteção. Verifique se a mudança introduz caminhos frágeis, silenciosos ou sem validação suficiente."
            )

        extension = Path(file_path).suffix.lower()
        if extension in {".yml", ".yaml", ".json", ".toml", ".ini", ".env"}:
            hints.append(
                "O arquivo parece ser de configuração ou infraestrutura. Verifique impacto em ambiente, integração, ordem de execução, segredos e compatibilidade entre ambientes."
            )

        hints.append(
            "Antes de resumir a mudança, tente identificar inconsistências entre a intenção aparente da alteração e o que o código realmente faz."
        )
        hints.append(
            "Se o diff não for suficiente, use tools para buscar evidências adicionais em arquivos relacionados, implementações conectadas, testes existentes e documentação oficial da stack quando necessário."
        )
        hints.append(
            "Priorize defeitos concretos ou suspeitas fortes sustentadas por evidência. Evite riscos genéricos sem base observável."
        )
        hints.append(
            "Não assuma framework, arquitetura ou domínio específico. Analise a mudança a partir de coerência, contrato, integração, cobertura e regressão."
        )

        return "\n".join(f"- {hint}" for hint in hints)

    def run(
        self,
        file_path: str,
        file_diff: str,
        code_content: str,
        repo_path: str,
        all_changed_files: Optional[list[str]] = None,
    ) -> str:
        debug_logger = None
        if DebugLogger is not None:
            repo_name = Path(repo_path).name
            debug_logger = DebugLogger.for_file_analysis(repo_name=repo_name, file_path=file_path)
            debug_logger.write_json(
                "input.json",
                {
                    "file_path": file_path,
                    "repo_path": repo_path,
                    "all_changed_files": all_changed_files or [],
                    "diff_length": len(file_diff),
                    "code_length": len(code_content),
                },
            )
            debug_logger.write_text("diff.patch", file_diff)
            debug_logger.write_text("current_file.txt", code_content)

        context_builder = RepoContextBuilder(repo_path)
        repo_context = context_builder.build(
            changed_file=file_path,
            code_content=code_content,
        )
        change_hints = self._build_change_hints(file_path, file_diff, code_content)

        if debug_logger:
            debug_logger.write_text("repo_context.txt", repo_context)
            debug_logger.write_text("change_hints.txt", change_hints)

        agent = QAAgentFactory(
            self.settings,
            repo_path=repo_path,
            debug_logger=debug_logger,
        ).create()

        task = QATaskFactory.create(
            agent=agent,
            file_path=file_path,
            file_diff=file_diff,
            code_content=code_content,
            repo_context=repo_context,
            change_hints=change_hints,
            all_changed_files=all_changed_files or [],
            debug_logger=debug_logger,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )

        try:
            result = crew.kickoff()
        except Exception as exc:
            if debug_logger:
                debug_logger.write_text("error.txt", repr(exc))
            raise

        if hasattr(result, "tasks_output") and result.tasks_output:
            task_output = result.tasks_output[-1]
            if hasattr(task_output, "raw") and task_output.raw:
                if debug_logger:
                    debug_logger.write_text("result.md", task_output.raw)
                return task_output.raw

        if hasattr(result, "raw") and result.raw:
            if debug_logger:
                debug_logger.write_text("result.md", result.raw)
            return result.raw

        final_result = str(result)
        if debug_logger:
            debug_logger.write_text("result.md", final_result)
        return final_result
