from src.services.token_budget_planner import TokenBudgetPlanner


def test_skips_small_documentation_change() -> None:
    planner = TokenBudgetPlanner()

    plan = planner.plan(
        file_path="docs/readme.md",
        file_diff="diff --git a/docs/readme.md b/docs/readme.md\n+novo texto\n",
        code_content="# Docs\n",
        cooperative_requested=True,
    )

    assert plan.analysis_mode == "skip"
    assert plan.context_level == "none"
    assert plan.include_full_file is False
    assert plan.include_memory is False


def test_small_low_risk_change_disables_cooperative_mode() -> None:
    planner = TokenBudgetPlanner()

    plan = planner.plan(
        file_path="src/utils/formatters.py",
        file_diff="+return value.strip()\n",
        code_content="def clean(value):\n    return value.strip()\n",
        cooperative_requested=True,
    )

    assert plan.analysis_mode == "standard"
    assert plan.context_level == "compact"
    assert "reduzida para QA padrão" in plan.reason


def test_high_risk_path_can_use_cooperative_mode() -> None:
    planner = TokenBudgetPlanner()

    plan = planner.plan(
        file_path="src/services/payment_service.py",
        file_diff="+def charge():\n+    return True\n",
        code_content="def charge():\n    return True\n",
        cooperative_requested=True,
    )

    assert plan.analysis_mode == "cooperative"
    assert plan.context_level == "standard"
    assert plan.include_memory is True


def test_large_file_uses_snippet_instead_of_full_file() -> None:
    planner = TokenBudgetPlanner()

    plan = planner.plan(
        file_path="src/services/user_service.py",
        file_diff="+value = 1\n",
        code_content="x" * 12_001,
    )

    assert plan.include_full_file is False
    assert plan.risk_hint == "high"
