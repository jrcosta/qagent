from src.schemas.generated_test_review_result import GeneratedTestsReviewResult


QAGENT_TEST_REVIEW_MEMORY_TAG = "#qagent-test-review"


def build_test_review_comment(findings: list[dict]) -> str:
    """Build the PR comment published by the test reviewer agent."""
    if not findings:
        return (
            f"{QAGENT_TEST_REVIEW_MEMORY_TAG}\n\n"
            "### ✅ QAgent: Revisão Crítica de Testes\n\n"
            "Todos os testes gerados foram analisados e aprovados nos critérios "
            "de qualidade e padrões do projeto."
        )

    summary_comment = (
        f"{QAGENT_TEST_REVIEW_MEMORY_TAG}\n\n"
        "### 🔍 QAgent: Revisão Crítica de Testes\n\n"
        "Foram identificados pontos de atenção nos testes gerados:\n\n"
    )

    for finding in findings:
        summary_comment += f"#### 📄 `{finding['file']}`\n"
        summary_comment += f"**Status:** {finding['status']}\n"
        summary_comment += f"**Resumo:** {finding['summary']}\n"

        issues = finding.get("issues") or []
        if issues:
            summary_comment += "**Problemas:**\n"
            for issue in issues:
                severity = issue.get("severity", "INFO")
                desc = issue.get("description", "")
                suggested_fix = issue.get("suggested_fix")
                summary_comment += f"- [{severity}] {desc}\n"
                if suggested_fix:
                    summary_comment += f"  Sugestão: {suggested_fix}\n"

        missing_scenarios = finding.get("missing_scenarios") or []
        if missing_scenarios:
            summary_comment += "**Cenários ausentes:**\n"
            for scenario in missing_scenarios:
                summary_comment += f"- {scenario}\n"

        suggested_fixes = finding.get("suggested_fixes") or []
        if suggested_fixes:
            summary_comment += "**Correções recomendadas:**\n"
            for fix in suggested_fixes:
                summary_comment += f"- {fix}\n"

        summary_comment += "\n"

    return summary_comment


def review_result_to_finding(
    file_path: str,
    review_result: GeneratedTestsReviewResult,
) -> dict | None:
    """Convert a review result with actionable feedback to a serializable finding."""
    normalized_status = _normalize_review_status(review_result)
    has_actionable_feedback = _has_actionable_feedback(review_result)

    if normalized_status == "APPROVED" and not has_actionable_feedback:
        return None

    return {
        "file": file_path,
        "status": normalized_status,
        "summary": review_result.summary,
        "issues": [
            issue.model_dump() if hasattr(issue, "model_dump") else issue
            for issue in review_result.issues
        ],
        "missing_scenarios": list(review_result.missing_scenarios),
        "suggested_fixes": list(review_result.suggested_fixes),
    }


def _normalize_review_status(review_result: GeneratedTestsReviewResult) -> str:
    if review_result.status != "APPROVED":
        return review_result.status

    if any(issue.severity == "ERROR" for issue in review_result.issues):
        return "INVALID"

    if _has_actionable_feedback(review_result):
        return "NEEDS_CHANGES"

    return "APPROVED"


def _has_actionable_feedback(review_result: GeneratedTestsReviewResult) -> bool:
    return bool(
        review_result.issues
        or review_result.missing_scenarios
        or review_result.suggested_fixes
    )
