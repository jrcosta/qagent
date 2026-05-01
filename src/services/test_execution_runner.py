import subprocess
import time
from typing import Optional
from src.schemas.test_execution_result import TestExecutionResult

class TestExecutionRunner:

    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def detect_command(self) -> str:
        # Simplificado (pode evoluir depois)
        return "pytest"

    def run(self) -> TestExecutionResult:
        command = self.detect_command()

        start = time.time()

        process = subprocess.Popen(
            [command],
            shell=False,
            cwd=self.repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        stdout, stderr = process.communicate()
        duration = time.time() - start

        return TestExecutionResult(
            success=process.returncode == 0,
            exit_code=process.returncode,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            command=command
        )
