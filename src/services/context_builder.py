from pathlib import Path
from typing import Iterable

from src.tools.repo_tools import (
    FindRelatedTestFilesTool,
    ListFilesInRepoTool,
    ReadFileTool,
    SearchInRepoTool,
)
from src.schemas.context_result import ContextResult



class RepoContextBuilder:
    MAX_SAME_NAME_HITS = 20
    MAX_RELATED_SOURCE_FILES = 4
    MAX_RELATED_TEST_FILES = 8
    MAX_TEST_FILE_SCAN = 500
    MAX_CHARS_PER_FILE = 3000
    TEST_DIR_MARKERS = (
        "/test/",
        "/tests/",
        "/spec/",
        "/specs/",
        "__tests__",
        "__test__",
    )

    TEST_FILE_TOKENS = (
        "test",
        "tests",
        "spec",
        "specs",
    )

    def __init__(self, repo_path: str) -> None:
        self.repo_path = Path(repo_path)

        self.read_file_tool = ReadFileTool(self.repo_path)
        self.search_tool = SearchInRepoTool(self.repo_path)
        self.list_files_tool = ListFilesInRepoTool(self.repo_path)
        self.related_tests_tool = FindRelatedTestFilesTool(self.repo_path)

    @staticmethod
    def _parse_tool_list(output: str) -> list[str]:
        if not output:
            return []

        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if not lines:
            return []

        no_result_tokens = (
            "Nenhum arquivo encontrado.",
            "Nenhum teste relacionado encontrado.",
        )

        if len(lines) == 1 and lines[0] in no_result_tokens:
            return []

        return lines

    @staticmethod
    def _is_test_file(path: str) -> bool:
        normalized = path.replace("\\", "/").lower()
        file_name = Path(path).name.lower()
        stem = Path(path).stem.lower()
        stem_tokens = [token for token in stem.replace("-", "_").split("_") if token]

        if any(marker in normalized for marker in RepoContextBuilder.TEST_DIR_MARKERS):
            return True

        if file_name.startswith("test") or file_name.endswith("test"):
            return True

        if ".test." in file_name or ".spec." in file_name:
            return True

        if file_name.endswith(("test.java", "tests.java", "spec.java", "specs.java")):
            return True

        if any(token in RepoContextBuilder.TEST_FILE_TOKENS for token in stem_tokens):
            return True

        return False

    @staticmethod
    def _unique(items: Iterable[str]) -> list[str]:
        unique_items: list[str] = []
        seen: set[str] = set()

        for item in items:
            if item in seen:
                continue
            seen.add(item)
            unique_items.append(item)

        return unique_items

    def _read_file_snippet(self, relative_path: str) -> str:
        content = self.read_file_tool._run(relative_path)

        if content.startswith("Arquivo não encontrado") or content.startswith("Caminho não é um arquivo"):
            return f"### {relative_path}\n{content}"

        snippet = content[: self.MAX_CHARS_PER_FILE]
        truncated = "\n... [TRUNCADO]" if len(content) > self.MAX_CHARS_PER_FILE else ""
        return f"### {relative_path}\n```\n{snippet}{truncated}\n```"

    def build(self, changed_file: str, code_content: str) -> ContextResult:
        stem = Path(changed_file).stem

        same_name_hits_text = self.search_tool._run(stem, max_results=self.MAX_SAME_NAME_HITS)
        same_name_hits = self._parse_tool_list(same_name_hits_text)

        related_tests_text = self.related_tests_tool._run(changed_file)
        related_tests = self._parse_tool_list(related_tests_text)

        all_files_text = self.list_files_tool._run(max_results=self.MAX_TEST_FILE_SCAN)
        all_files = self._parse_tool_list(all_files_text)

        existing_test_candidates = [path for path in all_files if self._is_test_file(path)]

        related_source_files = [
            path
            for path in same_name_hits
            if path != changed_file and not self._is_test_file(path)
        ]

        final_related_sources = self._unique(related_source_files)[: self.MAX_RELATED_SOURCE_FILES]
        final_existing_tests = self._unique(related_tests + existing_test_candidates)[: self.MAX_RELATED_TEST_FILES]

        related_source_contents = (
            "\n\n".join(self._read_file_snippet(path) for path in final_related_sources)
            if final_related_sources
            else "Nenhum arquivo de código relacionado encontrado."
        )

        existing_tests_contents = (
            "\n\n".join(self._read_file_snippet(path) for path in final_existing_tests)
            if final_existing_tests
            else "Nenhum teste existente identificado no repositório."
        )

        context_sections = [
            f"# Arquivo alterado\n{changed_file}",
            f"# Nome base pesquisado\n{stem}",
            "# Arquivos que parecem relacionados ao nome/base\n"
            + ("\n".join(same_name_hits) if same_name_hits else "Nenhum arquivo encontrado."),
            "# Testes existentes identificados\n"
            + ("\n".join(final_existing_tests) if final_existing_tests else "Nenhum teste encontrado."),
            f"# Conteúdo de código relacionado (amostra)\n{related_source_contents}",
            f"# Conteúdo de testes existentes (amostra)\n{existing_tests_contents}",
        ]

        summary_text = "\n\n".join(context_sections)

        return ContextResult(
            file_path=changed_file,
            summary=summary_text,
            related_files=same_name_hits,
            existing_tests=final_existing_tests,
            risks_from_context=[]
        )