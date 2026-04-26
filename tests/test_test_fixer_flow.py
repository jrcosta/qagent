from src.main_test_reviewer import (
    _filter_test_file_paths,
    _render_review_result_for_fixer,
)
from src.schemas.generated_test_review_result import (
    GeneratedTestIssue,
    GeneratedTestsReviewResult,
)
from src.tasks.test_fixer_task import TestFixerTaskFactory


class FakeTask:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class DummyAgent:
    pass


def test_render_review_result_for_fixer_includes_actionable_details() -> None:
    result = GeneratedTestsReviewResult(
        status="INVALID",
        summary="Testes falham no CI por expectativa especulativa.",
        issues=[
            GeneratedTestIssue(
                severity="ERROR",
                description="Teste espera 422, mas API retorna 200.",
                related_test="test_cart_rejects_extra_fields",
                suggested_fix="Ajustar teste para contrato atual.",
            )
        ],
        suggested_fixes=["Remover expectativa de extra_forbidden."],
    )

    rendered = _render_review_result_for_fixer(result)

    assert "Status: INVALID" in rendered
    assert "Teste espera 422, mas API retorna 200." in rendered
    assert "test_cart_rejects_extra_fields" in rendered
    assert "Remover expectativa de extra_forbidden." in rendered


def test_test_fixer_task_requires_file_blocks_and_ci_context(monkeypatch) -> None:
    monkeypatch.setattr("src.tasks.test_fixer_task.Task", FakeTask)

    task = TestFixerTaskFactory.create(
        agent=DummyAgent(),
        file_path="app/schemas.py",
        code_content="class CartRequest: pass",
        generated_tests="def test_cart(): pass",
        review_summary="Status: INVALID",
        ci_execution_summary="FAILED tests/test_api.py::test_cart",
    )

    assert "Resultado real do CI" in task.description
    assert "FAILED tests/test_api.py::test_cart" in task.description
    assert "### FILE: <caminho_relativo_do_arquivo_de_teste>" in task.description
    assert "Não altere código de produção" in task.description


def test_filter_test_file_paths_rejects_production_files() -> None:
    files = {
        "python-api/tests/test_api.py": "test",
        "java-api/src/test/java/UserServiceTest.java": "test",
        "javascript-api/src/users.test.js": "test",
        "python-api/app/schemas.py": "production",
    }

    filtered = _filter_test_file_paths(files)

    assert "python-api/tests/test_api.py" in filtered
    assert "java-api/src/test/java/UserServiceTest.java" in filtered
    assert "javascript-api/src/users.test.js" in filtered
    assert "python-api/app/schemas.py" not in filtered
