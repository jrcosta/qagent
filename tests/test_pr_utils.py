import os
import unittest
from unittest.mock import patch

from src.utils.pr_utils import build_pr_body


class BuildPrBodyTests(unittest.TestCase):
    def test_includes_full_qa_report_when_body_fits_limit(self):
        qa_report = "Resumo de QA pequeno"

        with patch.dict(os.environ, {"QAGENT_PR_BODY_MAX_CHARS": "10000"}):
            body = build_pr_body(
                qa_report=qa_report,
                test_files=["tests/test_user.py"],
                analyzed_files=["src/user.py"],
            )

        self.assertIn(qa_report, body)
        self.assertIn("Clique para ver o relatório de QA completo", body)

    def test_returns_compact_message_when_body_exceeds_limit(self):
        qa_report = "Achado importante de QA\n" * 100

        with patch.dict(os.environ, {"QAGENT_PR_BODY_MAX_CHARS": "500"}):
            body = build_pr_body(
                qa_report=qa_report,
                test_files=["tests/test_user.py"],
                analyzed_files=["src/user.py"],
            )

        self.assertIn("excedeu o limite seguro", body)
        self.assertIn("Agente: resuma o relatório de QA", body)
        self.assertNotIn("Clique para ver o relatório de QA completo", body)
        self.assertLess(len(body), len(qa_report))


if __name__ == "__main__":
    unittest.main()
