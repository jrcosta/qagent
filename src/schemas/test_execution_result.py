from pydantic import BaseModel
from typing import Optional

class TestExecutionResult(BaseModel):
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    command: str
