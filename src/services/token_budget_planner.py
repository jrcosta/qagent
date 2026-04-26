from __future__ import annotations

from pathlib import Path

from src.schemas.token_budget import TokenBudgetPlan


class TokenBudgetPlanner:
    """Decide quanto contexto cada arquivo deve consumir antes das chamadas LLM."""

    SMALL_DIFF_LINES = 80
    LARGE_DIFF_LINES = 300
    LARGE_FILE_CHARS = 12_000

    COMPACT_CONTEXT_CHARS = 4_000
    STANDARD_CONTEXT_CHARS = 8_000
    EXPANDED_CONTEXT_CHARS = 14_000

    TRIVIAL_EXTENSIONS = {
        ".md",
        ".markdown",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".lock",
    }
    TEST_MARKERS = ("/test/", "/tests/", "/spec/", "/specs/", "__tests__")
    HIGH_RISK_PATH_TOKENS = (
        "auth",
        "security",
        "permission",
        "payment",
        "billing",
        "migration",
        "database",
        "repository",
        "controller",
        "service",
        "workflow",
        "ci",
    )

    def plan(
        self,
        file_path: str,
        file_diff: str,
        code_content: str,
        cooperative_requested: bool = False,
    ) -> TokenBudgetPlan:
        diff_lines = _count_changed_lines(file_diff)
        change_size = self._classify_change_size(diff_lines)
        risk_hint = self._risk_hint(file_path, diff_lines)
        trivial = self._is_trivial_file(file_path)

        if trivial and change_size == "small":
            return TokenBudgetPlan(
                file_path=file_path,
                change_size=change_size,
                risk_hint="low",
                analysis_mode="skip",
                context_level="none",
                include_full_file=False,
                include_memory=False,
                max_context_chars=0,
                reason=(
                    "Mudança pequena em arquivo sem lógica executável; "
                    "review LLM não é necessária."
                ),
            )

        if cooperative_requested and not (
            change_size == "small" and risk_hint != "high"
        ):
            analysis_mode = "cooperative"
            context_level = "standard"
            max_context_chars = self.STANDARD_CONTEXT_CHARS
            reason = "Análise cooperativa solicitada e mudança não é pequena/trivial."
        else:
            analysis_mode = "standard"
            context_level = self._context_level(change_size, risk_hint)
            max_context_chars = self._max_context_chars(context_level)
            if cooperative_requested:
                reason = (
                    "Análise cooperativa solicitada, mas reduzida para QA padrão "
                    "por orçamento determinístico."
                )
            else:
                reason = "QA padrão escolhido pelo orçamento determinístico."

        include_full_file = len(code_content) <= self.LARGE_FILE_CHARS
        include_memory = risk_hint in {"medium", "high"} and not trivial

        return TokenBudgetPlan(
            file_path=file_path,
            change_size=change_size,
            risk_hint=risk_hint,
            analysis_mode=analysis_mode,
            context_level=context_level,
            include_full_file=include_full_file,
            include_memory=include_memory,
            max_context_chars=max_context_chars,
            reason=reason,
        )

    def _classify_change_size(self, diff_lines: int) -> str:
        if diff_lines < self.SMALL_DIFF_LINES:
            return "small"
        if diff_lines < self.LARGE_DIFF_LINES:
            return "medium"
        return "large"

    def _risk_hint(self, file_path: str, diff_lines: int) -> str:
        normalized = file_path.replace("\\", "/").lower()

        if any(token in normalized for token in self.HIGH_RISK_PATH_TOKENS):
            return "high"
        if self._is_test_file(normalized) or diff_lines >= self.SMALL_DIFF_LINES:
            return "medium"
        return "low"

    def _context_level(self, change_size: str, risk_hint: str) -> str:
        if risk_hint == "high" or change_size == "large":
            return "expanded"
        if risk_hint == "medium" or change_size == "medium":
            return "standard"
        return "compact"

    def _max_context_chars(self, context_level: str) -> int:
        if context_level == "expanded":
            return self.EXPANDED_CONTEXT_CHARS
        if context_level == "standard":
            return self.STANDARD_CONTEXT_CHARS
        if context_level == "compact":
            return self.COMPACT_CONTEXT_CHARS
        return 0

    def _is_trivial_file(self, file_path: str) -> bool:
        suffix = Path(file_path).suffix.lower()
        return suffix in self.TRIVIAL_EXTENSIONS

    def _is_test_file(self, normalized_path: str) -> bool:
        file_name = Path(normalized_path).name
        return (
            any(marker in normalized_path for marker in self.TEST_MARKERS)
            or ".test." in file_name
            or ".spec." in file_name
            or file_name.startswith("test_")
            or file_name.endswith("_test.py")
        )


def _count_changed_lines(file_diff: str) -> int:
    count = 0
    for line in file_diff.splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith(("+", "-")):
            count += 1
    return count
