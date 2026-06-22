from pathlib import Path

from src.config.settings import Settings
from src.services.analysis_pipeline import RepositoryAnalysisPipeline


def test_analysis_pipeline_exports_agentic_artifact_for_trivial_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# Projeto\nDocumentação atualizada.\n", encoding="utf-8")
    monkeypatch.setattr(
        "src.services.analysis_pipeline.get_changed_files",
        lambda repo, base, head: ["README.md"],
    )
    monkeypatch.setattr(
        "src.services.analysis_pipeline.get_file_diff",
        lambda file_path, repo, base, head: "- antigo\n+ novo",
    )
    monkeypatch.setattr(
        "src.services.analysis_pipeline.index_project_knowledge",
        lambda repo: None,
    )

    result = RepositoryAnalysisPipeline(Settings(llm_api_key="")).run(
        repo_path=tmp_path,
        output_file=tmp_path / "outputs" / "analysis.md",
        agentic_runtime=True,
    )

    assert len(result.artifacts) == 1
    artifact = result.artifacts[0]
    assert artifact.token_budget_plan is not None
    assert artifact.token_budget_plan.analysis_mode == "skip"
    assert artifact.agentic_run_status == "COMPLETED"
    assert artifact.test_generation_recommendation == "SKIPPED"
    assert result.artifacts_file.exists()
    assert result.summary_file.exists()
