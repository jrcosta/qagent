from pathlib import Path

from src.tools.repo_tools import (
    FindRelatedTestFilesTool,
    ListFilesInRepoTool,
    ReadFileTool,
    SearchInRepoTool,
)


class RepoContextBuilder:
    def __init__(self, repo_path: str) -> None:
        self.repo_path = Path(repo_path)

        self.read_file_tool = ReadFileTool(self.repo_path)
        self.search_tool = SearchInRepoTool(self.repo_path)
        self.list_files_tool = ListFilesInRepoTool(self.repo_path)
        self.related_tests_tool = FindRelatedTestFilesTool(self.repo_path)

    def build(self, changed_file: str, code_content: str) -> str:
        file_name = Path(changed_file).name
        stem = Path(changed_file).stem

        related_tests = self.related_tests_tool._run(changed_file)
        same_name_hits = self.search_tool._run(stem, max_results=10)

        context_sections = [
            f"# Arquivo alterado\n{changed_file}",
            f"# Nome base pesquisado\n{stem}",
            f"# Arquivos que parecem relacionados ao nome/base\n{same_name_hits}",
            f"# Arquivos de teste relacionados\n{related_tests}",
        ]

        return "\n\n".join(context_sections)