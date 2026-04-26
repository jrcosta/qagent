import re

from src.agent.test_generator_agent import TestGeneratorAgentFactory
from src.config.settings import Settings
from src.services.context_builder import RepoContextBuilder
from src.tasks.test_generator_task import TestGeneratorTaskFactory
from src.tools.memory_tools import QueryMemoriesTool
from crewai import Crew, Process
from src.schemas.context_result import render_context_result_for_prompt
from src.schemas.review_result import ReviewResult
from src.schemas.test_strategy_result import TestStrategyResult, render_test_strategy_result_for_prompt
from src.schemas.token_budget import TokenBudgetPlan




class TestGeneratorCrewRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.last_memory_query = ""
        self.last_memories_raw = ""
        self.last_memories_used: list[dict] = []
        self.last_context_result = None

    def _load_memories(self, file_path: str, code_content: str, limit: int) -> str:
        """Find relevant memories from the DB using semantic search."""
        self.last_memory_query = f"Testes para {file_path}. Código: {code_content[:200]}"
        self.last_memories_raw = ""
        self.last_memories_used = []

        try:
            tool = QueryMemoriesTool()
            result = tool._run(query=self.last_memory_query, limit=limit)
            self.last_memories_raw = result
            self.last_memories_used = _parse_memory_result(result)

            if result and "Nenhuma memória" not in result:
                count = len(self.last_memories_used)
                print(f"  🧠 Memories loaded: {count} relevant lesson(s) found for {file_path}")
                print(f"  🧠 Memory content preview: {result[:200]}...")
            else:
                print(f"  🧠 No relevant memories found in DB for {file_path}.")
            return result
        except Exception as exc:
            print(f"  ⚠️ Could not load memories: {exc}")
            return ""

    def run(
        self,
        qa_report: str,
        file_path: str,
        code_content: str,
        repo_path: str,
        test_strategy: TestStrategyResult | None = None,
        review_result: ReviewResult | None = None,
        token_budget_plan: TokenBudgetPlan | None = None,
        risk_level: str = "LOW",
    ) -> str:
        context_builder = RepoContextBuilder(repo_path)
        context_result = context_builder.build(
            changed_file=file_path,
            code_content=code_content,
            context_level=(
                token_budget_plan.context_level if token_budget_plan else "standard"
            ),
            max_context_chars=(
                token_budget_plan.max_context_chars if token_budget_plan else None
            ),
        )
        self.last_context_result = context_result
        
        repo_context_text = render_context_result_for_prompt(context_result)

        memory_limit = _memory_limit_for_risk(risk_level)
        if token_budget_plan is not None and not token_budget_plan.include_memory:
            memories = ""
            print(f"  🧠 Memory lookup SKIPPED by token budget for '{file_path}'")
        else:
            memories = self._load_memories(file_path, code_content, memory_limit)

        test_strategy_text = ""
        if test_strategy is not None:
            test_strategy_text = render_test_strategy_result_for_prompt(test_strategy)

        compact_qa_report = qa_report
        if review_result is not None:
            compact_qa_report = render_compact_generation_report(
                review_result=review_result,
                test_strategy=test_strategy,
            )

        agent = TestGeneratorAgentFactory(self.settings).create()
        task = TestGeneratorTaskFactory.create(
            agent=agent,
            qa_report=compact_qa_report,
            file_path=file_path,
            code_content=code_content,
            repo_context=repo_context_text,
            memories=memories,
            test_strategy_text=test_strategy_text,
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )

        result = crew.kickoff()

        if hasattr(result, "tasks_output") and result.tasks_output:
            task_output = result.tasks_output[-1]
            if hasattr(task_output, "raw") and task_output.raw:
                return task_output.raw

        if hasattr(result, "raw") and result.raw:
            return result.raw

        return str(result)


def _parse_memory_result(result: str) -> list[dict]:
    if not result or "Nenhuma memória" in result:
        return []

    memories: list[dict] = []
    blocks = [block.strip() for block in result.strip().split("\n\n") if block.strip()]
    pattern = re.compile(
        r"^\[distance=(?P<distance>[0-9.]+)\]\s+"
        r"\(PR #(?P<pr_number>\d+) em (?P<repo>.*?), por (?P<author>.*?)\)\n"
        r"\s*Lição:\s*(?P<lesson>.*)$",
        re.DOTALL,
    )

    for block in blocks:
        match = pattern.match(block)
        if not match:
            memories.append({"lesson": block})
            continue

        data = match.groupdict()
        memories.append(
            {
                "distance": float(data["distance"]),
                "pr_number": int(data["pr_number"]),
                "repo": data["repo"],
                "author": data["author"],
                "lesson": data["lesson"].strip(),
            }
        )

    return memories


def _memory_limit_for_risk(risk_level: str) -> int:
    if risk_level == "HIGH":
        return 5
    if risk_level == "MEDIUM":
        return 3
    return 2


def render_compact_generation_report(
    review_result: ReviewResult,
    test_strategy: TestStrategyResult | None = None,
) -> str:
    lines = ["Findings:"]
    if review_result.findings:
        for finding in review_result.findings:
            lines.append(f"- {finding.severity}: {finding.description}")
    else:
        lines.append("- Nenhum finding estruturado relevante.")

    lines.append("")
    lines.append("Test needs:")
    if review_result.test_needs:
        for need in review_result.test_needs:
            lines.append(f"- {need}")
    else:
        lines.append("- Nenhuma necessidade de teste extraída.")

    if test_strategy is not None and test_strategy.recommended_tests:
        lines.append("")
        lines.append("Strategy:")
        for test_case in test_strategy.recommended_tests:
            lines.append(
                f"- {test_case.test_type} {test_case.priority}: {test_case.name}"
            )

    return "\n".join(lines)
