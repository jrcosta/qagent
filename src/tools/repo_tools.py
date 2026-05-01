from pathlib import Path
from typing import List, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class ReadFileInput(BaseModel):
    file_path: str = Field(..., description="Caminho relativo do arquivo a ser lido.")


class SearchInRepoInput(BaseModel):
    term: str = Field(..., description="Termo a ser buscado no repositório.")
    max_results: int = Field(20, description="Quantidade máxima de arquivos retornados.")


class ListFilesInRepoInput(BaseModel):
    extension_filter: str | None = Field(
        default=None,
        description="Extensão opcional para filtrar arquivos, exemplo: .ts ou .tsx",
    )
    max_results: int = Field(100, description="Quantidade máxima de arquivos retornados.")


class FindRelatedTestFilesInput(BaseModel):
    changed_file: str = Field(..., description="Arquivo alterado para buscar testes relacionados.")


class ReadFileTool(BaseTool):
    name: str = "read_file"
    description: str = "Lê o conteúdo de um arquivo do repositório alvo a partir do caminho relativo."
    args_schema: Type[BaseModel] = ReadFileInput

    def __init__(self, repo_path: Path):
        super().__init__()
        self._repo_path = repo_path

    def _run(self, file_path: str) -> str:
        try:
            resolved = (self._repo_path / file_path).resolve()
        except Exception:
            return f"Caminho inválido: {file_path}"

        repo_root = self._repo_path.resolve()
        if not resolved.is_relative_to(repo_root):
            return "Acesso negado: caminho fora do repositório."

        if not resolved.exists():
            return f"Arquivo não encontrado: {file_path}"

        if not resolved.is_file():
            return f"Caminho não é um arquivo: {file_path}"

        try:
            return resolved.read_text(encoding="utf-8")
        except Exception as error:
            return f"Erro ao ler arquivo {file_path}: {error}"


class SearchInRepoTool(BaseTool):
    name: str = "search_in_repo"
    description: str = "Busca um termo no repositório e retorna caminhos relativos de arquivos onde o termo foi encontrado."
    args_schema: Type[BaseModel] = SearchInRepoInput

    def __init__(self, repo_path: Path):
        super().__init__()
        self._repo_path = repo_path

    def _run(self, term: str, max_results: int = 20) -> str:
        matches: List[str] = []

        for path in self._repo_path.rglob("*"):
            if not path.is_file():
                continue

            if ".git" in path.parts or "__pycache__" in path.parts or "node_modules" in path.parts:
                continue

            try:
                content = path.read_text(encoding="utf-8")
            except Exception:
                continue

            if term in content:
                relative_path = str(path.relative_to(self._repo_path))
                matches.append(relative_path)

            if len(matches) >= max_results:
                break

        if not matches:
            return "Nenhum arquivo encontrado."

        return "\n".join(matches)


class ListFilesInRepoTool(BaseTool):
    name: str = "list_files_in_repo"
    description: str = "Lista arquivos do repositório, com filtro opcional por extensão."
    args_schema: Type[BaseModel] = ListFilesInRepoInput

    def __init__(self, repo_path: Path):
        super().__init__()
        self._repo_path = repo_path

    def _run(self, extension_filter: str | None = None, max_results: int = 100) -> str:
        files: List[str] = []

        for path in self._repo_path.rglob("*"):
            if not path.is_file():
                continue

            if ".git" in path.parts or "__pycache__" in path.parts or "node_modules" in path.parts:
                continue

            if extension_filter and path.suffix != extension_filter:
                continue

            files.append(str(path.relative_to(self._repo_path)))

            if len(files) >= max_results:
                break

        if not files:
            return "Nenhum arquivo encontrado."

        return "\n".join(files)


class FindRelatedTestFilesTool(BaseTool):
    name: str = "find_related_test_files"
    description: str = "Procura arquivos de teste relacionados ao arquivo alterado com base no nome."
    args_schema: Type[BaseModel] = FindRelatedTestFilesInput

    def __init__(self, repo_path: Path):
        super().__init__()
        self._repo_path = repo_path

    def _run(self, changed_file: str) -> str:
        changed_path = Path(changed_file)
        stem = changed_path.stem.lower()

        related: List[str] = []

        for path in self._repo_path.rglob("*"):
            if not path.is_file():
                continue

            if ".git" in path.parts or "__pycache__" in path.parts or "node_modules" in path.parts:
                continue

            name = path.name.lower()

            if stem in name and ("test" in name or "spec" in name):
                related.append(str(path.relative_to(self._repo_path)))

        if not related:
            return "Nenhum teste relacionado encontrado."

        return "\n".join(related)