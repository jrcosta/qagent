from __future__ import annotations

from pathlib import Path

from src.schemas.automation import AutomationJob
from src.schemas.coordinator_state import CoordinatorState
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.services.artifact_exporter import load_artifacts_from_json


QAGENT_AUTONOMOUS_COMMENT_MARKER = "<!-- qagent-autonomous-feedback -->"
DEFAULT_MAX_COMMENT_CHARS = 60_000
MAX_FILE_ROWS = 25
MAX_TEST_ROWS = 40


class GitHubPrFeedbackPublisher:
    """Publica ou atualiza o comentário consolidado do QAgent em um PR."""

    def __init__(
        self,
        *,
        github_token: str,
        max_comment_chars: int = DEFAULT_MAX_COMMENT_CHARS,
        github_client=None,
    ) -> None:
        if not github_token and github_client is None:
            raise ValueError("GITHUB_TOKEN é obrigatório para publicar feedback")
        self.max_comment_chars = max_comment_chars
        if github_client is not None:
            self.github = github_client
        else:
            try:
                from github import Github
            except ImportError as exc:
                raise RuntimeError(
                    "PyGithub não instalado; execute pip install -r requirements.txt"
                ) from exc
            self.github = Github(github_token)

    def publish(
        self,
        *,
        job: AutomationJob,
        state: CoordinatorState,
    ) -> str | None:
        if job.event_name != "pull_request" or job.pr_number is None:
            return None
        body = build_autonomous_pr_comment(
            job=job,
            state=state,
            max_chars=self.max_comment_chars,
        )
        repository = self.github.get_repo(job.repository)
        issue = repository.get_issue(number=job.pr_number)
        for comment in issue.get_comments():
            if QAGENT_AUTONOMOUS_COMMENT_MARKER in comment.body:
                comment.edit(body)
                return getattr(comment, "html_url", None)
        created = issue.create_comment(body)
        return getattr(created, "html_url", None)


def build_autonomous_pr_comment(
    *,
    job: AutomationJob,
    state: CoordinatorState,
    max_chars: int = DEFAULT_MAX_COMMENT_CHARS,
) -> str:
    artifacts = _load_artifacts_safely(state.artifacts_file)
    risk_counts = _risk_counts(artifacts)
    generated_tests = _generated_test_files(artifacts)
    status_emoji = _status_emoji(state.status)
    body = "\n".join(
        [
            QAGENT_AUTONOMOUS_COMMENT_MARKER,
            f"## {status_emoji} QAgent: análise autônoma",
            "",
            f"**Status:** `{state.status}`",
            f"**Run:** `{state.run_id}`",
            f"**Head SHA:** `{job.head_sha}`",
            f"**Arquivos analisados:** {len(artifacts)}",
            f"**Arquivos elegíveis para testes:** {state.eligible_files}",
            f"**Escalações:** {state.escalated_files}",
            "",
            "### Distribuição de risco",
            "",
            f"- HIGH: {risk_counts['HIGH']}",
            f"- MEDIUM: {risk_counts['MEDIUM']}",
            f"- LOW: {risk_counts['LOW']}",
            "",
            "### Principais recomendações",
            "",
            _render_recommendations(artifacts),
            "",
            "### Arquivos com testes gerados",
            "",
            _render_generated_tests(generated_tests),
            "",
            "### Artefatos",
            "",
            _render_artifacts(state),
            "",
            _render_human_gate(state),
        ]
    ).strip()
    if len(body) <= max_chars:
        return body
    return _compact_comment(job, state, risk_counts, len(artifacts))


def _load_artifacts_safely(
    artifacts_file: str | None,
) -> list[FileAnalysisArtifact]:
    if not artifacts_file:
        return []
    try:
        return load_artifacts_from_json(artifacts_file)
    except Exception:
        return []


def _risk_counts(
    artifacts: list[FileAnalysisArtifact],
) -> dict[str, int]:
    counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    for artifact in artifacts:
        counts[artifact.risk_level] = counts.get(artifact.risk_level, 0) + 1
    return counts


def _generated_test_files(
    artifacts: list[FileAnalysisArtifact],
) -> list[str]:
    files: list[str] = []
    for artifact in artifacts:
        files.extend(artifact.generated_test_files.keys())
    return sorted(set(files))


def _render_recommendations(
    artifacts: list[FileAnalysisArtifact],
) -> str:
    if not artifacts:
        return "- Nenhum artefato estruturado disponível."
    lines: list[str] = []
    for artifact in artifacts[:MAX_FILE_ROWS]:
        summary = (
            artifact.review_result.summary
            if artifact.review_result
            else "Sem resumo estruturado."
        )
        test_count = (
            len(artifact.test_strategy_result.recommended_tests)
            if artifact.test_strategy_result
            else 0
        )
        lines.append(
            f"- `{artifact.file_path}` — risco `{artifact.risk_level}`, "
            f"{test_count} teste(s) recomendado(s). {summary}"
        )
    hidden = len(artifacts) - MAX_FILE_ROWS
    if hidden > 0:
        lines.append(f"- ... e mais {hidden} arquivo(s).")
    return "\n".join(lines)


def _render_generated_tests(test_files: list[str]) -> str:
    if not test_files:
        return "- Nenhum arquivo de teste gerado nesta execução."
    visible = test_files[:MAX_TEST_ROWS]
    lines = [f"- `{file_path}`" for file_path in visible]
    hidden = len(test_files) - len(visible)
    if hidden > 0:
        lines.append(f"- ... e mais {hidden} arquivo(s).")
    return "\n".join(lines)


def _render_artifacts(state: CoordinatorState) -> str:
    lines = []
    if state.analysis_report_file:
        lines.append(f"- Relatório: `{_display_path(state.analysis_report_file)}`")
    if state.artifacts_file:
        lines.append(f"- JSON estruturado: `{_display_path(state.artifacts_file)}`")
    if not lines:
        lines.append("- Artefatos não disponíveis.")
    return "\n".join(lines)


def _render_human_gate(state: CoordinatorState) -> str:
    if state.status == "ESCALATED":
        return (
            "### Revisão humana necessária\n\n"
            "O QAgent escalou esta execução. Revise os achados antes de aprovar."
        )
    if state.status == "FAILED":
        return (
            "### Execução falhou\n\n"
            f"Erro registrado: `{state.error or 'não informado'}`"
        )
    return (
        "### Próximo passo\n\n"
        "Use este comentário como apoio à revisão. Aprovação humana continua obrigatória."
    )


def _compact_comment(
    job: AutomationJob,
    state: CoordinatorState,
    risk_counts: dict[str, int],
    total_artifacts: int,
) -> str:
    return "\n".join(
        [
            QAGENT_AUTONOMOUS_COMMENT_MARKER,
            "## QAgent: análise autônoma",
            "",
            "O comentário completo excedeu o limite seguro de publicação.",
            "",
            f"- Status: `{state.status}`",
            f"- Run: `{state.run_id}`",
            f"- Head SHA: `{job.head_sha}`",
            f"- Arquivos analisados: {total_artifacts}",
            f"- Risco HIGH/MEDIUM/LOW: {risk_counts['HIGH']}/"
            f"{risk_counts['MEDIUM']}/{risk_counts['LOW']}",
            f"- Artefatos: `{_display_path(state.artifacts_file)}`",
        ]
    )


def _display_path(path: str | None) -> str:
    if not path:
        return "não disponível"
    try:
        return str(Path(path))
    except TypeError:
        return path


def _status_emoji(status: str) -> str:
    if status == "ESCALATED":
        return "⚠️"
    if status == "FAILED":
        return "❌"
    return "✅"
