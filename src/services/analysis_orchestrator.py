"""
Orquestrador responsável por coordenar o pipeline de análise
de um único arquivo após a etapa de QA review.

Centraliza a sequência: avaliação de risco → estratégia de testes
→ enriquecimento HIGH risk → avaliação final, eliminando duplicação
entre os entrypoints (main.py / main_test_generator.py).
"""

import time

from src.crew.high_risk_strategy_crew import HighRiskTestStrategyRunner
from src.schemas.file_analysis_artifact import FileAnalysisArtifact
from src.services.artifact_evaluator import evaluate_artifact
from src.services.test_strategy_builder import build_test_strategy_from_review


class AnalysisOrchestrator:
    """
    Coordena as etapas pós-QA review para um único arquivo.

    Recebe um ``FileAnalysisArtifact`` já construído (com review_result
    preenchido) e executa, em ordem:

    1. Avaliação de risco inicial
    2. Construção da estratégia de testes
    3. Enriquecimento via agente HIGH risk (quando aplicável)
    4. Avaliação final (atualiza test_generation_recommendation)

    Toda a observabilidade (durations, steps, policies) é registrada
    diretamente no artefato.
    """

    def __init__(self, high_risk_runner: HighRiskTestStrategyRunner) -> None:
        self._high_risk_runner = high_risk_runner

    def run_artifact_pipeline(
        self, artifact: FileAnalysisArtifact,
    ) -> FileAnalysisArtifact:
        """
        Executa o pipeline completo de avaliação e estratégia sobre
        o artefato fornecido. Retorna o mesmo artefato, mutado.
        """
        self._evaluate_risk(artifact)
        self._build_strategy(artifact)
        self._enrich_high_risk(artifact)
        self._evaluate_final(artifact)
        return artifact

    # ------------------------------------------------------------------
    # Etapas internas
    # ------------------------------------------------------------------

    @staticmethod
    def _evaluate_risk(artifact: FileAnalysisArtifact) -> None:
        """Avalia risco inicial com base nos findings da review."""
        t0 = time.perf_counter()
        evaluate_artifact(artifact)
        artifact.record_duration("evaluate_risk", (time.perf_counter() - t0) * 1000)
        artifact.mark_step_executed("evaluate_risk")

    @staticmethod
    def _build_strategy(artifact: FileAnalysisArtifact) -> None:
        """Constrói estratégia adaptativa baseada no risco."""
        t0 = time.perf_counter()
        test_strategy_result = build_test_strategy_from_review(
            file_path=artifact.file_path,
            review_result=artifact.review_result,
            risk_level=artifact.risk_level,
        )
        artifact.test_strategy_result = test_strategy_result
        artifact.record_duration("build_strategy", (time.perf_counter() - t0) * 1000)
        artifact.mark_step_executed("build_strategy")
        artifact.add_policy(f"strategy_{artifact.risk_level}")

    def _enrich_high_risk(self, artifact: FileAnalysisArtifact) -> None:
        """Aciona agente especializado HIGH risk quando aplicável."""
        if artifact.risk_level != "HIGH":
            artifact.mark_step_skipped(
                "high_risk_enrichment", f"risk_level={artifact.risk_level}",
            )
            return

        print(f"  🔬 Acionando agente especializado HIGH risk para: {artifact.file_path}")
        t0 = time.perf_counter()
        artifact.test_strategy_result = self._high_risk_runner.run(
            file_path=artifact.file_path,
            review_result=artifact.review_result,
            base_strategy=artifact.test_strategy_result,
            context_result=artifact.context_result,
        )
        artifact.record_duration(
            "high_risk_enrichment", (time.perf_counter() - t0) * 1000,
        )
        artifact.mark_step_executed("high_risk_enrichment")
        artifact.add_policy("high_risk_llm_enrichment")

    @staticmethod
    def _evaluate_final(artifact: FileAnalysisArtifact) -> None:
        """Reavalia o artefato após a estratégia estar completa."""
        evaluate_artifact(artifact)
        artifact.mark_step_executed("evaluate_final")
