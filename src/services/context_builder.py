
from __future__ import annotations

from src.tools.repo_tools import (
    FindRelatedTestFilesTool,
    ListFilesInRepoTool,
    ReadFileTool,
    SearchInRepoTool,
)


class RepoContextBuilder:
    def __init__(self, repo_path: str) -> None:
        self.repo_path = repo_path
        self.read_file_tool = ReadFileTool(repo_path=self.repo_path)
        self.search_tool = SearchInRepoTool(repo_path=self.repo_path)
        self.list_files_tool = ListFilesInRepoTool(repo_path=self.repo_path)
        self.related_tests_tool = FindRelatedTestFilesTool(repo_path=self.repo_path)

    def build(self, changed_file: str, code_content: str) -> str:
        parts: list[str] = []

        parts.append("## Arquivo alterado")
        parts.append(changed_file)

        parts.append("\n## Testes relacionados prováveis")
        parts.append(self.related_tests_tool.run(changed_file=changed_file))

        filename = changed_file.split("/")[-1]
        stem = filename.rsplit(".", 1)[0] if "." in filename else filename

        parts.append("\n## Arquivos potencialmente relacionados por nome")
        parts.append(self.search_tool.run(query=stem, use_regex=False, max_results=20))

        parts.append("\n## Estrutura relevante do repositório")
        parent_dir = changed_file.rsplit("/", 1)[0] if "/" in changed_file else ""
        pattern = f"{parent_dir}/*" if parent_dir else "*"
        parts.append(self.list_files_tool.run(pattern=pattern, max_results=60))

        # Pequena heurística opcional: se houver imports em Python, buscar arquivos citados
        if "import " in code_content or "from " in code_content:
            parts.append("\n## Pistas adicionais por imports aparentes")
            lines = [line.strip() for line in code_content.splitlines() if line.strip().startswith(("import ", "from "))]
            parts.append("\n".join(lines[:20]))

        return "\n".join(parts).strip()
