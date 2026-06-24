from pathlib import Path
from types import SimpleNamespace

from src.schemas.automation import AutomationJob
from src.schemas.coordinator_state import CoordinatorState
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.schemas.review_result import ReviewResult
from src.schemas.test_strategy_result import TestCase as StrategyTestCase
from src.schemas.test_strategy_result import TestStrategyResult as StrategyResult
from src.services.artifact_exporter import export_artifacts_to_json
from src.services.github_pr_feedback import (
    QAGENT_AUTONOMOUS_COMMENT_MARKER,
    GitHubPrFeedbackPublisher,
    build_autonomous_pr_comment,
)


def _job() -> AutomationJob:
    return AutomationJob(
        delivery_id="delivery-1",
        repository="owner/repo",
        event_name="pull_request",
        action="synchronize",
        base_sha="base",
        head_sha="head",
        pr_number=42,
        available_at="2026-06-23T00:00:00+00:00",
        created_at="2026-06-23T00:00:00+00:00",
        updated_at="2026-06-23T00:00:00+00:00",
    )


def _state(tmp_path: Path, *, status: str = "COMPLETED") -> CoordinatorState:
    artifact = FileAnalysisArtifact(
        file_path="src/service.py",
        review_result=ReviewResult(
            summary="Validação de regra crítica.",
            test_needs=["Cobrir erro de domínio"],
        ),
        test_strategy_result=StrategyResult(
            recommended_tests=[
                StrategyTestCase(
                    name="Erro de domínio",
                    priority="HIGH",
                )
            ]
        ),
        generated_test_files={"tests/test_service.py": "def test_service(): pass"},
        risk_level="HIGH",
    )
    artifacts_file = export_artifacts_to_json([artifact], str(tmp_path))
    return CoordinatorState(
        run_id="run-1",
        repo_path=str(tmp_path),
        output_dir=str(tmp_path),
        status=status,  # type: ignore[arg-type]
        artifacts_file=str(artifacts_file),
        analysis_report_file=str(tmp_path / "analysis.md"),
        eligible_files=1,
        escalated_files=1 if status == "ESCALATED" else 0,
    )


def test_build_autonomous_pr_comment_summarizes_artifacts(tmp_path) -> None:
    body = build_autonomous_pr_comment(
        job=_job(),
        state=_state(tmp_path, status="ESCALATED"),
    )

    assert QAGENT_AUTONOMOUS_COMMENT_MARKER in body
    assert "QAgent: análise autônoma" in body
    assert "`src/service.py`" in body
    assert "`tests/test_service.py`" in body
    assert "Revisão humana necessária" in body


class FakeComment:
    def __init__(self, body: str) -> None:
        self.body = body
        self.html_url = "https://github.com/owner/repo/pull/42#issuecomment-1"
        self.edited_body = None

    def edit(self, body: str) -> None:
        self.edited_body = body


class FakeIssue:
    def __init__(self, comments) -> None:
        self.comments = comments
        self.created_body = None

    def get_comments(self):
        return self.comments

    def create_comment(self, body: str):
        self.created_body = body
        return SimpleNamespace(
            html_url="https://github.com/owner/repo/pull/42#issuecomment-2"
        )


class FakeRepo:
    def __init__(self, issue: FakeIssue) -> None:
        self.issue = issue

    def get_issue(self, number: int):
        assert number == 42
        return self.issue


class FakeGithub:
    def __init__(self, issue: FakeIssue) -> None:
        self.issue = issue

    def get_repo(self, full_name: str):
        assert full_name == "owner/repo"
        return FakeRepo(self.issue)


def test_publisher_updates_existing_qagent_comment(tmp_path) -> None:
    existing = FakeComment(f"{QAGENT_AUTONOMOUS_COMMENT_MARKER}\nold")
    issue = FakeIssue([existing])
    publisher = GitHubPrFeedbackPublisher(
        github_token="",
        github_client=FakeGithub(issue),
    )

    url = publisher.publish(job=_job(), state=_state(tmp_path))

    assert url == existing.html_url
    assert existing.edited_body is not None
    assert "Validação de regra crítica" in existing.edited_body
    assert issue.created_body is None
