from pathlib import Path
from typing import List


class RepoTools:
    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path

    def read_file(self, file_path: str) -> str:
        path = self.repo_path / file_path

        if not path.exists():
            return f"Arquivo não encontrado: {file_path}"

        if not path.is_file():
            return f"Caminho não é um arquivo: {file_path}"

        try:
            return path.read_text(encoding="utf-8")
        except Exception as error:
            return f"Erro ao ler arquivo {file_path}: {error}"

    def search_in_repo(self, term: str, max_results: int = 20) -> List[str]:
        matches: List[str] = []

        for path in self.repo_path.rglob("*"):
            if not path.is_file():
                continue

            if ".git" in path.parts or "__pycache__" in path.parts or "node_modules" in path.parts:
                continue

            try:
                content = path.read_text(encoding="utf-8")
            except Exception:
                continue

            if term in content:
                relative_path = str(path.relative_to(self.repo_path))
                matches.append(relative_path)

            if len(matches) >= max_results:
                break

        return matches

    def list_files_in_repo(self, extension_filter: str | None = None, max_results: int = 100) -> List[str]:
        files: List[str] = []

        for path in self.repo_path.rglob("*"):
            if not path.is_file():
                continue

            if ".git" in path.parts or "__pycache__" in path.parts or "node_modules" in path.parts:
                continue

            if extension_filter and path.suffix != extension_filter:
                continue

            files.append(str(path.relative_to(self.repo_path)))

            if len(files) >= max_results:
                break

        return files

    def find_related_test_files(self, changed_file: str) -> List[str]:
        changed_path = Path(changed_file)
        stem = changed_path.stem.lower()

        related: List[str] = []

        for path in self.repo_path.rglob("*"):
            if not path.is_file():
                continue

            if ".git" in path.parts or "__pycache__" in path.parts or "node_modules" in path.parts:
                continue

            name = path.name.lower()

            if stem in name and ("test" in name or "spec" in name):
                related.append(str(path.relative_to(self.repo_path)))

        return related