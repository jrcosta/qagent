"""
Exportador de artefatos estruturados do pipeline.

Gera:
- artifacts.json: lista completa de FileAnalysisArtifact serializados
- run_summary.json: resumo agregado da execução
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.schemas.file_analysis_artifact import FileAnalysisArtifact


def export_artifacts_to_json(
    artifacts: list[FileAnalysisArtifact],
    output_dir: str,
) -> Path:
    """
    Serializa a lista de artefatos em JSON e salva em `output_dir/artifacts.json`.
    Retorna o Path do arquivo gerado.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    file_path = output_path / "artifacts.json"

    data = [_safe_model_dump(a) for a in artifacts]
    file_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return file_path


def load_artifacts_from_json(file_path: str | Path) -> list[FileAnalysisArtifact]:
    """
    Carrega o handoff estruturado produzido pela etapa de análise.

    Falha explicitamente quando o arquivo não existe, não contém uma lista ou
    possui um artefato incompatível com o contrato Pydantic atual.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de artefatos não encontrado: {path}")

    raw_data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, list):
        raise ValueError("artifacts.json deve conter uma lista de artefatos")

    return [FileAnalysisArtifact.model_validate(item) for item in raw_data]


def export_run_summary(
    artifacts: list[FileAnalysisArtifact],
    output_dir: str,
    total_duration_ms: float | None = None,
) -> Path:
    """
    Gera um resumo agregado da execução e salva em `output_dir/run_summary.json`.
    Retorna o Path do arquivo gerado.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    total_skipped = 0
    total_fallbacks = 0
    total_executed = 0
    all_policies: list[str] = []
    flow_counts: dict[str, int] = {}
    context_level_counts: dict[str, int] = {}

    for a in artifacts:
        risk_counts[a.risk_level] = risk_counts.get(a.risk_level, 0) + 1
        total_skipped += len(a.skipped_steps)
        total_fallbacks += len(a.fallbacks_triggered)
        total_executed += len(a.executed_steps)
        all_policies.extend(a.applied_policies)
        if a.token_budget_plan is not None:
            flow = a.token_budget_plan.analysis_mode
            context_level = a.token_budget_plan.context_level
            flow_counts[flow] = flow_counts.get(flow, 0) + 1
            context_level_counts[context_level] = (
                context_level_counts.get(context_level, 0) + 1
            )

    summary: dict[str, Any] = {
        "total_files": len(artifacts),
        "risk_distribution": risk_counts,
        "total_steps_executed": total_executed,
        "total_steps_skipped": total_skipped,
        "total_fallbacks_triggered": total_fallbacks,
        "policies_applied": sorted(set(all_policies)),
        "analysis_flow_distribution": flow_counts,
        "context_level_distribution": context_level_counts,
    }

    if total_duration_ms is not None:
        summary["total_duration_ms"] = round(total_duration_ms, 2)

    file_path = output_path / "run_summary.json"
    file_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return file_path


def _safe_model_dump(artifact: FileAnalysisArtifact) -> dict:
    """Serializa o artefato usando Pydantic, com fallback seguro."""
    try:
        return artifact.model_dump(mode="json")
    except Exception:
        return artifact.dict()
