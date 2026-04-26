from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

from src.schemas.ci_check_result import CIFailingCheck, CITestExecutionResult


TERMINAL_STATES = {"SUCCESS", "FAILURE", "CANCELLED", "SKIPPED"}
FAILURE_BUCKETS = {"fail", "cancel"}


class CIFailureCollector:
    """Consulta checks do PR alvo e compacta falhas para orientar a revisão."""

    def __init__(
        self,
        repo_path: Path,
        repo_full_name: str,
        branch_name: str = "",
        pr_url: str = "",
        timeout_seconds: int = 180,
        poll_interval_seconds: int = 10,
        max_log_chars: int = 8000,
    ) -> None:
        self.repo_path = repo_path
        self.repo_full_name = repo_full_name
        self.branch_name = branch_name
        self.pr_url = pr_url
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.max_log_chars = max_log_chars

    def collect(self) -> CITestExecutionResult:
        pr_ref = self._resolve_pr_ref()
        if not pr_ref:
            return CITestExecutionResult(
                status="unavailable",
                summary="CI não consultado: PR não encontrado para a branch informada.",
            )

        checks = self._wait_for_checks(pr_ref)
        if checks is None:
            return CITestExecutionResult(
                status="unavailable",
                pr_ref=pr_ref,
                summary="CI não consultado: GitHub CLI indisponível ou sem acesso aos checks.",
            )

        if not checks:
            return CITestExecutionResult(
                status="unavailable",
                pr_ref=pr_ref,
                summary="Nenhum check de CI encontrado para o PR alvo.",
            )

        failing = [
            c
            for c in checks
            if c.get("bucket") in FAILURE_BUCKETS or c.get("state") in {"FAILURE", "CANCELLED"}
        ]
        if failing:
            failing_checks = [self._build_failing_check(c) for c in failing]
            summary = _render_ci_summary("failed", pr_ref, failing_checks)
            return CITestExecutionResult(
                status="failed",
                pr_ref=pr_ref,
                summary=summary,
                failing_checks=failing_checks,
            )

        pending = [c for c in checks if c.get("state") not in TERMINAL_STATES]
        if pending:
            names = ", ".join(c.get("name", "check sem nome") for c in pending)
            return CITestExecutionResult(
                status="pending",
                pr_ref=pr_ref,
                summary=f"CI ainda pendente após aguardar: {names}.",
            )

        if not failing:
            return CITestExecutionResult(
                status="passed",
                pr_ref=pr_ref,
                summary="Todos os checks de CI do PR alvo passaram.",
            )

    def _resolve_pr_ref(self) -> str:
        if self.pr_url:
            return self.pr_url
        if not self.branch_name:
            return ""

        result = self._run_gh(
            [
                "pr",
                "list",
                "--repo",
                self.repo_full_name,
                "--head",
                self.branch_name,
                "--state",
                "open",
                "--json",
                "number,url",
                "--limit",
                "1",
            ]
        )
        if result.returncode != 0:
            return self.branch_name

        try:
            prs = json.loads(result.stdout)
        except json.JSONDecodeError:
            return self.branch_name

        if prs:
            return str(prs[0].get("number") or prs[0].get("url") or self.branch_name)
        return self.branch_name

    def _wait_for_checks(self, pr_ref: str) -> list[dict] | None:
        deadline = time.monotonic() + self.timeout_seconds
        last_checks: list[dict] | None = None

        while True:
            result = self._run_gh(
                [
                    "pr",
                    "checks",
                    pr_ref,
                    "--repo",
                    self.repo_full_name,
                    "--json",
                    "name,state,bucket,link,workflow",
                ]
            )
            if result.returncode != 0:
                return None

            try:
                checks = json.loads(result.stdout)
            except json.JSONDecodeError:
                return None

            last_checks = checks
            if checks and all(c.get("state") in TERMINAL_STATES for c in checks):
                return checks

            if time.monotonic() >= deadline:
                return last_checks

            time.sleep(self.poll_interval_seconds)

    def _build_failing_check(self, check: dict) -> CIFailingCheck:
        link = check.get("link", "")
        run_id = _extract_run_id(link)
        excerpt = ""
        if run_id:
            log_result = self._run_gh(
                ["run", "view", run_id, "--repo", self.repo_full_name, "--log-failed"]
            )
            if log_result.returncode == 0:
                excerpt = _compact_failure_log(log_result.stdout, self.max_log_chars)

        return CIFailingCheck(
            name=check.get("name", ""),
            workflow=check.get("workflow", ""),
            state=check.get("state", ""),
            bucket=check.get("bucket", ""),
            link=link,
            failure_excerpt=excerpt,
        )

    def _run_gh(self, args: list[str]) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        if env.get("GITHUB_TOKEN") and not env.get("GH_TOKEN"):
            env["GH_TOKEN"] = env["GITHUB_TOKEN"]

        return subprocess.run(
            ["gh"] + args,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            env=env,
        )


def render_ci_result_for_prompt(result: CITestExecutionResult) -> str:
    return result.summary


def _extract_run_id(link: str) -> str:
    match = re.search(r"/actions/runs/(\d+)", link)
    return match.group(1) if match else ""


def _compact_failure_log(log_text: str, max_chars: int) -> str:
    if not log_text:
        return ""

    lines = [line for line in log_text.splitlines() if line.strip()]
    interesting = [
        line
        for line in lines
        if "FAILED " in line
        or "FAILURES" in line
        or "Error:" in line
        or "AssertionError" in line
        or "DID NOT RAISE" in line
        or "assert " in line
        or "Process completed with exit code" in line
    ]
    compact = "\n".join(interesting or lines[-120:])
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars] + "\n... [LOG DE CI TRUNCADO]"


def _render_ci_summary(
    status: str,
    pr_ref: str,
    failing_checks: list[CIFailingCheck],
) -> str:
    lines = [
        f"Status agregado do CI: {status}",
        f"PR consultado: {pr_ref}",
        "",
        "Checks com falha/cancelamento:",
    ]
    for check in failing_checks:
        lines.append(
            f"- {check.name} ({check.workflow or 'workflow não informado'}): "
            f"{check.state or check.bucket}"
        )
        if check.link:
            lines.append(f"  Link: {check.link}")
        if check.failure_excerpt:
            lines.append("  Trecho de log:")
            lines.append(check.failure_excerpt)
    return "\n".join(lines)
