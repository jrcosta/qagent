from pathlib import Path

from crewai import Process

from src.config.settings import Settings
from src.crew.cooperative_analysis_crew import CooperativeAnalysisCrewRunner
from src.tasks.cooperative_analysis_task import CooperativeAnalysisTaskFactory


COOPERATIVE_MARKDOWN = """
# Tipo da mudança
Alteração em regra de negócio.

# Evidências observadas
- O diff altera a validação de entrada.

# Impacto provável
Pode afetar payloads inválidos.

# Riscos identificados
- crítico: Payload inválido pode ser aceito.

# Cenários de testes manuais
- Enviar payload inválido.

# Sugestões de testes unitários
- Validar rejeição de payload inválido.

# Sugestões de testes de integração
- Validar contrato da API.

# Sugestões de testes de carga ou desempenho
Não aplicável.

# Pontos que precisam de esclarecimento
- Confirmar regra de validação.

# Validação cooperativa
O gerente consolidou análise, estratégia e crítica.
"""


class FakeTaskOutput:
    raw = COOPERATIVE_MARKDOWN


class FakeCrewResult:
    tasks_output = [FakeTaskOutput()]


class FakeCrew:
    last_instance = None

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        FakeCrew.last_instance = self

    def kickoff(self) -> FakeCrewResult:
        return FakeCrewResult()


class FakeAgent:
    def __init__(self, role: str) -> None:
        self.role = role


class FakeAgentFactory:
    def __init__(self, role: str) -> None:
        self.role = role

    def create(self, tools: list | None = None) -> FakeAgent:
        return FakeAgent(self.role)


def test_cooperative_runner_uses_sequential_process(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("def validate(payload):\n    return bool(payload)\n", encoding="utf-8")

    monkeypatch.setattr("src.crew.cooperative_analysis_crew.Crew", FakeCrew)
    monkeypatch.setattr(
        "src.crew.cooperative_analysis_crew.CooperativeManagerAgentFactory",
        lambda settings: FakeAgentFactory("Gerente de Qualidade e Coordenação Multiagente"),
    )
    monkeypatch.setattr(
        "src.crew.cooperative_analysis_crew.QAAgentFactory",
        lambda settings: FakeAgentFactory("QA Sênior Investigador"),
    )
    monkeypatch.setattr(
        "src.crew.cooperative_analysis_crew.HighRiskStrategyAgentFactory",
        lambda settings: FakeAgentFactory(
            "Especialista em Estratégia de Testes para Código de Alto Risco"
        ),
    )
    monkeypatch.setattr(
        "src.crew.cooperative_analysis_crew.AnalysisCriticAgentFactory",
        lambda settings: FakeAgentFactory("Crítico de Análise de QA"),
    )

    runner = CooperativeAnalysisCrewRunner(Settings(llm_api_key="test-key"))
    result = runner.run(
        file_path="src/service.py",
        file_diff="- return True\n+ return bool(payload)",
        code_content=source.read_text(encoding="utf-8"),
        repo_path=str(tmp_path),
    )

    crew_kwargs = FakeCrew.last_instance.kwargs
    assert crew_kwargs["process"] == Process.sequential
    assert [agent.role for agent in crew_kwargs["agents"]] == [
        "QA Sênior Investigador",
        "Especialista em Estratégia de Testes para Código de Alto Risco",
        "Crítico de Análise de QA",
        "Gerente de Qualidade e Coordenação Multiagente",
    ]
    assert "Validação cooperativa" in result.raw_review_markdown
    assert result.review_result.findings
    assert result.review_result.test_needs


def test_cooperative_consolidation_task_preserves_parser_sections() -> None:
    task = CooperativeAnalysisTaskFactory.create_consolidation_task(
        file_path="src/service.py",
    )

    for heading in [
        "# Tipo da mudança",
        "# Evidências observadas",
        "# Impacto provável",
        "# Riscos identificados",
        "# Cenários de testes manuais",
        "# Sugestões de testes unitários",
        "# Sugestões de testes de integração",
        "# Pontos que precisam de esclarecimento",
        "# Validação cooperativa",
    ]:
        assert heading in task.description


def test_cooperative_task_compat_create_still_works() -> None:
    task = CooperativeAnalysisTaskFactory.create(
        file_path="src/service.py",
        file_diff="diff",
        code_content="code",
        repo_context="context",
    )
    assert task is not None
    assert "src/service.py" in task.description
