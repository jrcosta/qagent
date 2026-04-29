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


def test_test_fixer_task_requires_file_blocks_and_ci_context(monkeypatch) -> None:
    monkeypatch.setattr("src.tasks.test_fixer_task.Task", FakeTask)

    task = TestFixerTaskFactory.create(
        agent=DummyAgent(),
        file_path="app/schemas.py",
        code_content="class CartRequest: pass",
        test_strategy="My strategy",
        failed_tests="def test_cart(): pass",
        review_report="Status: INVALID",
    )

    assert "Status: INVALID" in task.description
    assert "def test_cart(): pass" in task.description
    assert "### FILE: <caminho_relativo_do_arquivo_de_teste>" in task.description
    assert "NÃO inclua explicações fora dos blocos de código." in task.description
