from src.services.test_execution_runner import TestExecutionRunner

def test_runner_executes():
    runner = TestExecutionRunner(repo_path=".")
    result = runner.run()

    assert result is not None
    assert isinstance(result.success, bool)
    assert result.command == "pytest"
