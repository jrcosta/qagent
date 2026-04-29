from src.services.test_execution_runner import TestExecutionRunner
TestExecutionRunner.__test__ = False


def test_runner_executes(monkeypatch):
    class DummyProcess:
        returncode = 0
        def communicate(self):
            return ("test output", "")

    def mock_popen(*args, **kwargs):
        return DummyProcess()

    monkeypatch.setattr("subprocess.Popen", mock_popen)

    runner = TestExecutionRunner(repo_path=".")
    result = runner.run()

    assert result is not None
    assert isinstance(result.success, bool)
    assert result.command == "pytest"
