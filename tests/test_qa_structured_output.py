from src.crew.qa_crew import extract_review_result
from src.schemas.review_result import (
    Finding,
    ReviewResult,
    render_review_result_as_markdown,
)
from src.tasks.qa_task import QATaskFactory


class FakeTask:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)
        self.markdown = kwargs.get("markdown", False)


class FakeTaskOutput:
    def __init__(
        self,
        *,
        raw: str = "",
        pydantic=None,
        json_dict=None,
    ) -> None:
        self.raw = raw
        self.pydantic = pydantic
        self.json_dict = json_dict


class FakeCrewResult:
    def __init__(self, task_output: FakeTaskOutput) -> None:
        self.tasks_output = [task_output]
        self.raw = task_output.raw


def _review() -> ReviewResult:
    return ReviewResult(
        summary="Mudança crítica na validação de autenticação.",
        findings=[
            Finding(
                description="Token expirado pode ser aceito",
                severity="ERROR",
                line_number=42,
            )
        ],
        test_needs=["Rejeitar token expirado"],
    )


def test_qa_task_declares_review_result_output(monkeypatch) -> None:
    monkeypatch.setattr("src.tasks.qa_task.Task", FakeTask)

    task = QATaskFactory.create(
        agent=object(),
        file_path="src/auth.py",
        file_diff="+ validate_token(token)",
        code_content="def validate_token(token): ...",
        repo_context="pytest",
    )

    assert task.output_pydantic is ReviewResult
    assert task.markdown is False


def test_extract_review_result_prefers_pydantic_output() -> None:
    expected = _review()
    result = FakeCrewResult(
        FakeTaskOutput(
            raw='{"summary": "raw JSON"}',
            pydantic=expected,
        )
    )

    review, raw, structured, reason = extract_review_result(result)

    assert review == expected
    assert raw == '{"summary": "raw JSON"}'
    assert structured is True
    assert reason == ""


def test_extract_review_result_accepts_json_dict() -> None:
    expected = _review()
    result = FakeCrewResult(
        FakeTaskOutput(
            raw='{"summary": "raw JSON"}',
            json_dict=expected.model_dump(),
        )
    )

    review, _, structured, reason = extract_review_result(result)

    assert review == expected
    assert structured is True
    assert reason == ""


def test_extract_review_result_falls_back_to_markdown() -> None:
    markdown = """
# Tipo da mudança
Alteração de autenticação.

# Impacto provável
Fluxo de login pode falhar.

# Riscos identificados
- crítico: Token expirado pode ser aceito.

# Sugestões de testes unitários
- Rejeitar token expirado.
"""
    result = FakeCrewResult(FakeTaskOutput(raw=markdown))

    review, raw, structured, reason = extract_review_result(result)

    assert raw == markdown
    assert structured is False
    assert review.findings[0].severity == "ERROR"
    assert review.test_needs == ["Rejeitar token expirado."]
    assert "Markdown interpretado" in reason


def test_render_review_result_as_markdown_is_presentation_only() -> None:
    markdown = render_review_result_as_markdown(_review())

    assert "# Resumo da análise" in markdown
    assert "[ERROR] Token expirado pode ser aceito (linha 42)" in markdown
    assert "Rejeitar token expirado" in markdown
