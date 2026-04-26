from src.tasks.test_reviewer_task import TestReviewerTaskFactory


class DummyAgent:
    pass


class FakeTask:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_reviewer_task_includes_ci_execution_summary(monkeypatch) -> None:
    monkeypatch.setattr("src.tasks.test_reviewer_task.Task", FakeTask)

    task = TestReviewerTaskFactory.create(
        agent=DummyAgent(),
        file_path="app/schemas.py",
        code_content="class CartRequest: pass",
        qa_report="Risco: validação de payload",
        test_strategy="Cobrir contrato real",
        generated_tests="def test_cart(): pass",
        ci_execution_summary="FAILED tests/test_schemas.py::test_cart_request",
    )

    assert "RESULTADO REAL DO CI DO PR" in task.description
    assert "FAILED tests/test_schemas.py::test_cart_request" in task.description
    assert "Use primeiro o resultado real do CI" in task.description
