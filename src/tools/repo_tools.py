
from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path
from typing import Any, ClassVar

from pydantic import Field

try:
    from crewai.tools import BaseTool
except Exception:  # pragma: no cover
    from crewai_tools import BaseTool  # type: ignore


class _NoOpLogger:
    def log_tool_start(self, tool_name: str, payload: dict[str, Any]) -> None:
        pass

    def log_tool_success(self, tool_name: str, payload: dict[str, Any]) -> None:
        pass

    def log_tool_error(self, tool_name: str, payload: dict[str, Any]) -> None:
        pass


class _RepoTool(BaseTool):
    repo_path: str = Field(..., description="Absolute path to repository root")
    debug_logger: Any | None = Field(default=None, exclude=True)

    model_config = {"arbitrary_types_allowed": True}

    def _root(self) -> Path:
        return Path(self.repo_path).resolve()

    def _logger(self) -> Any:
        return self.debug_logger or _NoOpLogger()

    def _safe_resolve(self, relative_path: str) -> Path:
        root = self._root()
        candidate = (root / relative_path).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError(f"Path outside repository: {relative_path}")
        return candidate

    def _iter_files(self):
        ignored_dirs = {
            ".git", ".venv", "venv", "__pycache__", "node_modules",
            ".mypy_cache", ".pytest_cache", "dist", "build", ".next",
            ".idea", ".vscode", "coverage", ".coverage"
        }
        root = self._root()
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in ignored_dirs for part in path.parts):
                continue
            yield path

    @staticmethod
    def _truncate(text: str, limit: int = 12000) -> str:
        if len(text) <= limit:
            return text
        return text[:limit] + "\n\n...[truncated]..."


class ReadFileTool(_RepoTool):
    name: str = "read_file"
    description: str = "Read a repository file by relative path and return its contents."

    def _run(self, file_path: str) -> str:
        logger = self._logger()
        logger.log_tool_start(self.name, {"file_path": file_path})
        try:
            target = self._safe_resolve(file_path)
            if not target.exists() or not target.is_file():
                raise FileNotFoundError(file_path)
            content = target.read_text(encoding="utf-8", errors="ignore")
            rel = str(target.relative_to(self._root()))
            result = f"# File: {rel}\n\n{self._truncate(content)}"
            logger.log_tool_success(self.name, {"file_path": file_path, "resolved_path": rel, "length": len(content)})
            return result
        except Exception as exc:
            logger.log_tool_error(self.name, {"file_path": file_path, "error": repr(exc)})
            return f"Error reading file '{file_path}': {exc}"


class SearchInRepoTool(_RepoTool):
    name: str = "search_in_repo"
    description: str = "Search repository text or regex pattern and return matching files with excerpts."

    def _run(self, query: str, use_regex: bool = False, max_results: int = 20) -> str:
        logger = self._logger()
        logger.log_tool_start(self.name, {"query": query, "use_regex": use_regex, "max_results": max_results})
        try:
            pattern = re.compile(query) if use_regex else None
            results: list[str] = []
            for file_path in self._iter_files():
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                for idx, line in enumerate(content.splitlines(), start=1):
                    matched = bool(pattern.search(line)) if use_regex else (query in line)
                    if matched:
                        rel = str(file_path.relative_to(self._root()))
                        results.append(f"{rel}:{idx}: {line.strip()}")
                        if len(results) >= max_results:
                            break
                if len(results) >= max_results:
                    break

            if not results:
                logger.log_tool_success(self.name, {"matches": 0})
                return f"No matches found for query: {query}"

            logger.log_tool_success(self.name, {"matches": len(results)})
            return self._truncate("\n".join(results), 8000)
        except Exception as exc:
            logger.log_tool_error(self.name, {"query": query, "error": repr(exc)})
            return f"Error searching repository for '{query}': {exc}"


class ListFilesInRepoTool(_RepoTool):
    name: str = "list_files_in_repo"
    description: str = "List repository files, optionally filtered by glob pattern."

    def _run(self, pattern: str = "*", max_results: int = 200) -> str:
        logger = self._logger()
        logger.log_tool_start(self.name, {"pattern": pattern, "max_results": max_results})
        try:
            matches: list[str] = []
            root = self._root()
            for file_path in self._iter_files():
                rel = str(file_path.relative_to(root))
                if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(file_path.name, pattern):
                    matches.append(rel)
                    if len(matches) >= max_results:
                        break

            logger.log_tool_success(self.name, {"matches": len(matches), "pattern": pattern})
            if not matches:
                return f"No files found for pattern: {pattern}"
            return "\n".join(matches)
        except Exception as exc:
            logger.log_tool_error(self.name, {"pattern": pattern, "error": repr(exc)})
            return f"Error listing files for pattern '{pattern}': {exc}"


class FindRelatedTestFilesTool(_RepoTool):
    name: str = "find_related_test_files"
    description: str = "Find likely related automated test files for a changed file."

    TEST_PATTERNS: ClassVar[list[str]] = [
        "test_*.py", "*_test.py", "*.spec.ts", "*.test.ts", "*.spec.js", "*.test.js",
        "*Tests.java", "*Test.java", "*_spec.rb", "*_test.rb"
    ]

    def _run(self, changed_file: str, max_results: int = 10) -> str:
        logger = self._logger()
        logger.log_tool_start(self.name, {"changed_file": changed_file, "max_results": max_results})
        try:
            changed_path = Path(changed_file)
            stem = changed_path.stem.lower()
            matches: list[tuple[int, str]] = []

            for file_path in self._iter_files():
                rel = str(file_path.relative_to(self._root()))
                filename = file_path.name
                if not any(fnmatch.fnmatch(filename, pattern) for pattern in self.TEST_PATTERNS):
                    continue

                score = 0
                name_lower = filename.lower()
                rel_lower = rel.lower()

                if stem and stem in name_lower:
                    score += 5
                if changed_path.parent.name and changed_path.parent.name.lower() in rel_lower:
                    score += 2
                if any(part.lower() in rel_lower for part in changed_path.parts if part):
                    score += 1

                if score > 0:
                    matches.append((score, rel))

            matches.sort(key=lambda item: (-item[0], item[1]))
            top = [path for _, path in matches[:max_results]]

            logger.log_tool_success(self.name, {"matches": len(top)})
            if not top:
                return f"No related test files found for: {changed_file}"
            return "\n".join(top)
        except Exception as exc:
            logger.log_tool_error(self.name, {"changed_file": changed_file, "error": repr(exc)})
            return f"Error finding related test files for '{changed_file}': {exc}"


class InspectRepoStackTool(_RepoTool):
    name: str = "inspect_repo_stack"
    description: str = "Inspect repository to infer main languages, frameworks, manifest files and test tooling."

    MANIFESTS: ClassVar[dict[str, str]] = {
        "package.json": "Node.js/JavaScript",
        "pyproject.toml": "Python",
        "requirements.txt": "Python",
        "poetry.lock": "Python",
        "Pipfile": "Python",
        "pom.xml": "Java/Maven",
        "build.gradle": "Java/Gradle",
        "build.gradle.kts": "Java/Kotlin Gradle",
        "Cargo.toml": "Rust",
        "go.mod": "Go",
        "composer.json": "PHP",
        "Gemfile": "Ruby",
        "pubspec.yaml": "Dart/Flutter",
        "mix.exs": "Elixir",
    }

    EXTENSION_LANGUAGES: ClassVar[dict[str, str]] = {
        ".py": "Python",
        ".js": "JavaScript",
        ".jsx": "JavaScript/React",
        ".ts": "TypeScript",
        ".tsx": "TypeScript/React",
        ".java": "Java",
        ".kt": "Kotlin",
        ".go": "Go",
        ".rs": "Rust",
        ".rb": "Ruby",
        ".php": "PHP",
        ".cs": ".NET/C#",
        ".swift": "Swift",
        ".scala": "Scala",
        ".dart": "Dart",
        ".tf": "Terraform",
        ".sh": "Shell",
    }

    FRAMEWORK_HINTS: ClassVar[dict[str, list[str]]] = {
        "FastAPI": ["fastapi"],
        "Django": ["django"],
        "Flask": ["flask"],
        "Pytest": ["pytest"],
        "React": ["react"],
        "Next.js": ["next"],
        "Jest": ["jest"],
        "Vitest": ["vitest"],
        "Express": ["express"],
        "NestJS": ["@nestjs", "nestjs"],
        "Spring": ["spring-boot", "org.springframework", "springframework"],
        "JUnit": ["junit"],
        "Terraform": ["terraform", "provider"],
    }

    def _run(self) -> str:
        logger = self._logger()
        logger.log_tool_start(self.name, {})
        try:
            manifests: list[str] = []
            language_counts: dict[str, int] = {}
            detected_frameworks: set[str] = set()
            test_tools: set[str] = set()
            root = self._root()

            for file_path in self._iter_files():
                rel = str(file_path.relative_to(root))
                if file_path.name in self.MANIFESTS:
                    manifests.append(rel)

                language = self.EXTENSION_LANGUAGES.get(file_path.suffix.lower())
                if language:
                    language_counts[language] = language_counts.get(language, 0) + 1

            for manifest_rel in manifests[:20]:
                try:
                    content = (root / manifest_rel).read_text(encoding="utf-8", errors="ignore").lower()
                except Exception:
                    continue

                for framework, hints in self.FRAMEWORK_HINTS.items():
                    if any(hint in content for hint in hints):
                        detected_frameworks.add(framework)

                if "pytest" in content:
                    test_tools.add("Pytest")
                if "junit" in content:
                    test_tools.add("JUnit")
                if "jest" in content:
                    test_tools.add("Jest")
                if "vitest" in content:
                    test_tools.add("Vitest")

            csproj_files = [str(p.relative_to(root)) for p in root.rglob("*.csproj")]
            if csproj_files:
                manifests.extend(csproj_files)
                language_counts[".NET/C#"] = language_counts.get(".NET/C#", 0) + len(csproj_files)

            ordered_languages = sorted(language_counts.items(), key=lambda item: (-item[1], item[0]))
            result = {
                "languages": [name for name, _ in ordered_languages[:8]],
                "frameworks": sorted(detected_frameworks),
                "test_tools": sorted(test_tools),
                "manifest_files": sorted(set(manifests))[:30],
            }
            logger.log_tool_success(self.name, result)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.log_tool_error(self.name, {"error": repr(exc)})
            return f"Error inspecting repository stack: {exc}"


class GetOfficialDocsReferenceTool(BaseTool):
    name: str = "get_official_docs_reference"
    description: str = "Return canonical official documentation links for a language, framework, test tool, or build tool."

    DOCS: ClassVar[dict[str, str]] = {
        "python": "https://docs.python.org/3/",
        "fastapi": "https://fastapi.tiangolo.com/",
        "django": "https://docs.djangoproject.com/",
        "flask": "https://flask.palletsprojects.com/",
        "pytest": "https://docs.pytest.org/",
        "javascript": "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
        "typescript": "https://www.typescriptlang.org/docs/",
        "node.js": "https://nodejs.org/docs/latest/api/",
        "node": "https://nodejs.org/docs/latest/api/",
        "react": "https://react.dev/",
        "next.js": "https://nextjs.org/docs",
        "next": "https://nextjs.org/docs",
        "jest": "https://jestjs.io/docs/getting-started",
        "vitest": "https://vitest.dev/guide/",
        "java": "https://docs.oracle.com/en/java/",
        "spring": "https://docs.spring.io/spring-boot/documentation.html",
        "junit": "https://junit.org/junit5/docs/current/user-guide/",
        "maven": "https://maven.apache.org/guides/",
        "gradle": "https://docs.gradle.org/current/userguide/userguide.html",
        "go": "https://go.dev/doc/",
        "rust": "https://doc.rust-lang.org/",
        "ruby": "https://www.ruby-lang.org/en/documentation/",
        "rails": "https://guides.rubyonrails.org/",
        "php": "https://www.php.net/docs.php",
        ".net": "https://learn.microsoft.com/dotnet/",
        "c#": "https://learn.microsoft.com/dotnet/csharp/",
        "terraform": "https://developer.hashicorp.com/terraform/docs",
        "shell": "https://www.gnu.org/software/bash/manual/",
    }

    def _run(self, technology: str) -> str:
        key = technology.strip().lower()
        if key in self.DOCS:
            return self.DOCS[key]
        simplified = key.replace("framework", "").strip()
        if simplified in self.DOCS:
            return self.DOCS[simplified]
        return f"No official documentation mapping found for: {technology}"


__all__ = [
    "ReadFileTool",
    "SearchInRepoTool",
    "ListFilesInRepoTool",
    "FindRelatedTestFilesTool",
    "InspectRepoStackTool",
    "GetOfficialDocsReferenceTool",
]
