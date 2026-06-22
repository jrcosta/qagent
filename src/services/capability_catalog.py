from src.schemas.agentic_runtime import (
    CapabilityDefinition,
    CapabilityName,
    ExecutionPlan,
    PlanStep,
)


CAPABILITY_CATALOG: dict[CapabilityName, CapabilityDefinition] = {
    "evaluate_risk": CapabilityDefinition(
        name="evaluate_risk",
        description="Classifica risco e qualidade usando regras determinísticas.",
    ),
    "build_test_strategy": CapabilityDefinition(
        name="build_test_strategy",
        description="Constrói estratégia tipada de testes conforme o risco.",
        requires=["evaluate_risk"],
    ),
    "enrich_high_risk": CapabilityDefinition(
        name="enrich_high_risk",
        description="Refina via LLM apenas estratégias classificadas como HIGH.",
        requires=["build_test_strategy"],
    ),
    "evaluate_final": CapabilityDefinition(
        name="evaluate_final",
        description="Reavalia a recomendação final após a estratégia.",
        requires=["build_test_strategy"],
    ),
}


def render_capability_catalog() -> str:
    lines = []
    for capability in CAPABILITY_CATALOG.values():
        requirements = ", ".join(capability.requires) or "nenhuma"
        lines.append(
            f"- {capability.name}: {capability.description} "
            f"Dependências: {requirements}."
        )
    return "\n".join(lines)


def validate_execution_plan(plan: ExecutionPlan) -> None:
    """Policy gate executado antes de qualquer capability."""
    if len(plan.steps) > 8:
        raise ValueError("o planner não pode criar mais de 8 passos iniciais")

    capabilities = [step.capability for step in plan.steps]
    if capabilities[0] != "evaluate_risk":
        raise ValueError("o plano deve começar por evaluate_risk")
    if capabilities[-1] != "evaluate_final":
        raise ValueError("o plano deve terminar por evaluate_final")
    if capabilities.count("evaluate_risk") != 1:
        raise ValueError("o plano deve conter exatamente um evaluate_risk")
    if capabilities.count("build_test_strategy") != 1:
        raise ValueError("o plano deve conter exatamente um build_test_strategy")
    if capabilities.count("evaluate_final") != 1:
        raise ValueError("o plano deve conter exatamente um evaluate_final")

    steps_by_id = {step.id: step for step in plan.steps}
    for index, step in enumerate(plan.steps):
        if step.capability not in CAPABILITY_CATALOG:
            raise ValueError(f"capability não autorizada: {step.capability}")

        required_capabilities = set(CAPABILITY_CATALOG[step.capability].requires)
        previous_capabilities = {
            previous.capability for previous in plan.steps[:index]
        }
        missing = required_capabilities - previous_capabilities
        if missing:
            raise ValueError(
                f"capability '{step.capability}' sem pré-requisitos: {sorted(missing)}"
            )

        ancestor_capabilities = {
            steps_by_id[ancestor_id].capability
            for ancestor_id in _ancestor_ids(step, steps_by_id)
        }
        missing_dependencies = required_capabilities - ancestor_capabilities
        if missing_dependencies:
            raise ValueError(
                f"capability '{step.capability}' sem dependências explícitas para: "
                f"{sorted(missing_dependencies)}"
            )


def _ancestor_ids(step: PlanStep, steps_by_id: dict[str, PlanStep]) -> set[str]:
    ancestors: set[str] = set()
    pending = list(step.depends_on)
    while pending:
        dependency_id = pending.pop()
        if dependency_id in ancestors:
            continue
        ancestors.add(dependency_id)
        pending.extend(steps_by_id[dependency_id].depends_on)
    return ancestors
