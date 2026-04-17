from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

try:
    from src.utils.debug_logger import DebugLogger
except Exception:  # pragma: no cover
    DebugLogger = None  # type: ignore


IGNORED_PARTS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".idea", ".pytest_cache"}


def _should_skip(path: Path) -> bool:
    return any(part in IGNORED_PARTS for part in path.parts)


def _read_text_safe(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="latin-1")
        except Exception:
            return None
    except Exception:
        return None


class ReadFileInput(BaseModel):
    file_path: str = Field(..., description="Caminho relativo do arquivo a ser lido no repositório alvo.")


class SearchInRepoInput(BaseModel):
    term: str = Field(..., description="Termo a ser buscado no repositório alvo.")
    max_results: int = Field(20, description="Quantidade máxima de arquivos retornados.")


class ListFilesInRepoInput(BaseModel):
    extension_filter: str | None = Field(default=None, description="Extensão opcional para filtrar arquivos, exemplo: .py, .ts, .java")
    max_results: int = Field(100, description="Quantidade máxima de arquivos retornados.")


class FindRelatedTestFilesInput(BaseModel):
    changed_file: str = Field(..., description="Arquivo alterado para buscar testes relacionados por nome e convenção.")


class InspectRepoStackInput(BaseModel):
    max_files: int = Field(300, description="Quantidade máxima de arquivos a inspecionar para inferir a stack do repositório.")


class GetOfficialDocsReferenceInput(BaseModel):
    technology: str = Field(..., description="Tecnologia, linguagem, framework ou ferramenta para obter a documentação oficial canônica.")


class _RepoTool(BaseTool):
    def __init__(self, repo_path: Path, debug_logger: Optional[DebugLogger] = None):
        super().__init__()
        self._repo_path = repo_path
        self._debug_logger = debug_logger

    def _log(self, event: str, payload: dict) -> None:
        if self._debug_logger:
            self._debug_logger.log_tool_event(event, payload)


class ReadFileTool(_RepoTool):
    name: str = "read_file"
    description: str = "Lê o conteúdo de um arquivo do repositório alvo a partir do caminho relativo. Use para inspecionar implementações, testes, manifestos e configuração." 
    args_schema: Type[BaseModel] = ReadFileInput

    def _run(self, file_path: str) -> str:
        self._log("START", {"tool": self.name, "file_path": file_path})
        path = self._repo_path / file_path

        if not path.exists():
            result = f"Arquivo não encontrado: {file_path}"
            self._log("ERROR", {"tool": self.name, "file_path": file_path, "error": result})
            return result

        if not path.is_file():
            result = f"Caminho não é um arquivo: {file_path}"
            self._log("ERROR", {"tool": self.name, "file_path": file_path, "error": result})
            return result

        content = _read_text_safe(path)
        if content is None:
            result = f"Não foi possível ler arquivo como texto: {file_path}"
            self._log("ERROR", {"tool": self.name, "file_path": file_path, "error": result})
            return result

        truncated = content[:12000]
        if len(content) > len(truncated):
            truncated += "\n\n[TRUNCADO: arquivo muito grande para leitura completa pela tool]"

        self._log("SUCCESS", {"tool": self.name, "file_path": file_path, "length": len(truncated)})
        return truncated


class SearchInRepoTool(_RepoTool):
    name: str = "search_in_repo"
    description: str = "Busca um termo no repositório e retorna caminhos relativos dos arquivos em que o termo foi encontrado. Use para localizar usos, referências e testes relacionados." 
    args_schema: Type[BaseModel] = SearchInRepoInput

    def _run(self, term: str, max_results: int = 20) -> str:
        self._log("START", {"tool": self.name, "term": term, "max_results": max_results})
        matches: List[str] = []
        needle = term.lower()

        for path in self._repo_path.rglob("*"):
            if not path.is_file() or _should_skip(path):
                continue

            content = _read_text_safe(path)
            if content is None:
                continue

            if needle in content.lower() or needle in path.name.lower():
                matches.append(str(path.relative_to(self._repo_path)))
                if len(matches) >= max_results:
                    break

        if not matches:
            result = "Nenhum arquivo encontrado."
            self._log("SUCCESS", {"tool": self.name, "matches": 0})
            return result

        result = "\n".join(matches)
        self._log("SUCCESS", {"tool": self.name, "matches": len(matches)})
        return result


class ListFilesInRepoTool(_RepoTool):
    name: str = "list_files_in_repo"
    description: str = "Lista arquivos do repositório, com filtro opcional por extensão. Use para descobrir estrutura, manifestos e convenções do projeto." 
    args_schema: Type[BaseModel] = ListFilesInRepoInput

    def _run(self, extension_filter: str | None = None, max_results: int = 100) -> str:
        self._log("START", {"tool": self.name, "extension_filter": extension_filter, "max_results": max_results})
        files: List[str] = []

        for path in self._repo_path.rglob("*"):
            if not path.is_file() or _should_skip(path):
                continue
            if extension_filter and path.suffix != extension_filter:
                continue

            files.append(str(path.relative_to(self._repo_path)))
            if len(files) >= max_results:
                break

        if not files:
            result = "Nenhum arquivo encontrado."
            self._log("SUCCESS", {"tool": self.name, "files": 0})
            return result

        result = "\n".join(files)
        self._log("SUCCESS", {"tool": self.name, "files": len(files)})
        return result


class FindRelatedTestFilesTool(_RepoTool):
    name: str = "find_related_test_files"
    description: str = "Procura arquivos de teste relacionados ao arquivo alterado com base no nome, na convenção e no nome base do módulo." 
    args_schema: Type[BaseModel] = FindRelatedTestFilesInput

    def _run(self, changed_file: str) -> str:
        self._log("START", {"tool": self.name, "changed_file": changed_file})
        changed_path = Path(changed_file)
        stem = changed_path.stem.lower()
        parent_name = changed_path.parent.name.lower() if changed_path.parent.name else ""

        related: List[str] = []

        for path in self._repo_path.rglob("*"):
            if not path.is_file() or _should_skip(path):
                continue

            name = path.name.lower()
            rel = str(path.relative_to(self._repo_path))
            is_test_name = any(token in name for token in ("test", "spec"))
            if not is_test_name:
                continue

            score = 0
            if stem and stem in name:
                score += 2
            if parent_name and parent_name in rel.lower():
                score += 1
            if changed_path.stem.replace("_", "") and changed_path.stem.replace("_", "") in name.replace("_", ""):
                score += 1

            if score > 0:
                related.append(rel)

        if not related:
            result = "Nenhum teste relacionado encontrado."
            self._log("SUCCESS", {"tool": self.name, "matches": 0})
            return result

        unique_related = list(dict.fromkeys(related))[:20]
        result = "\n".join(unique_related)
        self._log("SUCCESS", {"tool": self.name, "matches": len(unique_related)})
        return result


class InspectRepoStackTool(_RepoTool):
    name: str = "inspect_repo_stack"
    description: str = "Inspeciona o repositório para inferir linguagem, framework, ferramentas de build, testes e manifestos. Use quando a análise depender da semântica da stack." 
    args_schema: Type[BaseModel] = InspectRepoStackInput

    MANIFESTS = {
        "package.json": "Node.js/JavaScript",
        "pyproject.toml": "Python",
        "requirements.txt": "Python",
        "pom.xml": "Java/Maven",
        "build.gradle": "Java/Gradle",
        "Cargo.toml": "Rust",
        "go.mod": "Go",
        "composer.json": "PHP",
        "Gemfile": "Ruby",
        "pubspec.yaml": "Dart/Flutter",
        "mix.exs": "Elixir",
        "*.csproj": ".NET",
    }

    DOC_HINTS = {
        "fastapi": "FastAPI",
        "django": "Django",
        "flask": "Flask",
        "pytest": "pytest",
        "unittest": "Python unittest",
        "jest": "Jest",
        "vitest": "Vitest",
        "react": "React",
        "next": "Next.js",
        "express": "Express",
        "spring": "Spring",
        "junit": "JUnit 5",
        "laravel": "Laravel",
        "terraform": "Terraform",
    }

    def _run(self, max_files: int = 300) -> str:
        self._log("START", {"tool": self.name, "max_files": max_files})
        manifest_files: List[str] = []
        suffix_counter: dict[str, int] = {}
        detected_hints: set[str] = set()
        scanned = 0

        for path in self._repo_path.rglob("*"):
            if not path.is_file() or _should_skip(path):
                continue
            scanned += 1
            rel = str(path.relative_to(self._repo_path))
            suffix = path.suffix.lower()
            if suffix:
                suffix_counter[suffix] = suffix_counter.get(suffix, 0) + 1

            name = path.name
            if name in self.MANIFESTS or name.endswith(".csproj"):
                manifest_files.append(rel)

            if scanned <= max_files:
                content = _read_text_safe(path)
                if content:
                    low = content.lower()
                    for hint_key, hint_name in self.DOC_HINTS.items():
                        if hint_key in low:
                            detected_hints.add(hint_name)

        probable_languages: List[str] = []
        ext_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".tsx": "TypeScript/React",
            ".jsx": "JavaScript/React",
            ".java": "Java",
            ".kt": "Kotlin",
            ".go": "Go",
            ".rs": "Rust",
            ".rb": "Ruby",
            ".php": "PHP",
            ".cs": "C#/.NET",
            ".tf": "Terraform",
            ".swift": "Swift",
            ".dart": "Dart",
        }
        for suffix, language in ext_map.items():
            if suffix_counter.get(suffix):
                probable_languages.append(language)

        lines = [
            "# Stack inferida do repositório",
            f"Arquivos inspecionados: {scanned}",
            "",
            "## Linguagens prováveis",
            *(sorted(probable_languages) or ["Nenhuma linguagem inferida claramente."]),
            "",
            "## Manifestos e arquivos de build",
            *(sorted(manifest_files) or ["Nenhum manifesto conhecido encontrado."]),
            "",
            "## Tecnologias ou frameworks sugeridos por indícios no código",
            *(sorted(detected_hints) or ["Nenhuma tecnologia específica inferida com segurança."]),
        ]

        result = "\n".join(lines)
        self._log("SUCCESS", {"tool": self.name, "scanned": scanned, "languages": probable_languages, "hints": sorted(detected_hints)})
        return result


class GetOfficialDocsReferenceTool(_RepoTool):
    name: str = "get_official_docs_reference"
    description: str = "Retorna a URL canônica da documentação oficial de uma linguagem, framework ou ferramenta. Use quando a semântica da stack for importante para validar comportamento." 
    args_schema: Type[BaseModel] = GetOfficialDocsReferenceInput

    DOCS = {
        "python": "https://docs.python.org/3/",
        "python unittest": "https://docs.python.org/3/library/unittest.html",
        "pytest": "https://docs.pytest.org/",
        "fastapi": "https://fastapi.tiangolo.com/",
        "django": "https://docs.djangoproject.com/",
        "flask": "https://flask.palletsprojects.com/",
        "javascript": "https://developer.mozilla.org/docs/Web/JavaScript",
        "typescript": "https://www.typescriptlang.org/docs/",
        "node.js": "https://nodejs.org/docs/latest/api/",
        "node": "https://nodejs.org/docs/latest/api/",
        "react": "https://react.dev/",
        "next.js": "https://nextjs.org/docs",
        "next": "https://nextjs.org/docs",
        "express": "https://expressjs.com/",
        "java": "https://docs.oracle.com/en/java/",
        "spring": "https://docs.spring.io/spring-framework/reference/",
        "junit": "https://junit.org/junit5/docs/current/user-guide/",
        "junit 5": "https://junit.org/junit5/docs/current/user-guide/",
        "go": "https://go.dev/doc/",
        "rust": "https://doc.rust-lang.org/",
        "terraform": "https://developer.hashicorp.com/terraform/docs",
        "php": "https://www.php.net/docs.php",
        "laravel": "https://laravel.com/docs",
        "ruby": "https://www.ruby-lang.org/en/documentation/",
        "rails": "https://guides.rubyonrails.org/",
        "c#": "https://learn.microsoft.com/dotnet/csharp/",
        ".net": "https://learn.microsoft.com/dotnet/",
        "kotlin": "https://kotlinlang.org/docs/home.html",
        "swift": "https://www.swift.org/documentation/",
        "dart": "https://dart.dev/guides",
    }

    def _run(self, technology: str) -> str:
        normalized = technology.strip().lower()
        self._log("START", {"tool": self.name, "technology": normalized})
        url = self.DOCS.get(normalized)
        if not url:
            result = (
                "Documentação oficial não mapeada para esta tecnologia. "
                "Tente um termo mais específico como linguagem, framework ou ferramenta principal."
            )
            self._log("SUCCESS", {"tool": self.name, "mapped": False})
            return result

        result = f"Documentação oficial de {technology.strip()}: {url}"
        self._log("SUCCESS", {"tool": self.name, "mapped": True, "url": url})
        return result
