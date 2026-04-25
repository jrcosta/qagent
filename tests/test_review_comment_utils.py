import unittest

from src.schemas.generated_test_review_result import GeneratedTestsReviewResult
from src.utils.review_comment_utils import (
    QAGENT_TEST_REVIEW_MEMORY_TAG,
    build_test_review_comment,
    review_result_to_finding,
)


class ReviewCommentUtilsTests(unittest.TestCase):
    def test_comment_includes_memory_marker_when_approved(self):
        comment = build_test_review_comment([])

        self.assertIn(QAGENT_TEST_REVIEW_MEMORY_TAG, comment)
        self.assertIn("Todos os testes gerados foram analisados", comment)

    def test_comment_includes_findings_and_marker(self):
        comment = build_test_review_comment(
            [
                {
                    "file": "src/user.py",
                    "status": "NEEDS_CHANGES",
                    "summary": "Falta validar cenário de erro.",
                    "issues": [
                        {
                            "severity": "WARN",
                            "description": "Assert genérico demais.",
                            "suggested_fix": "Validar o payload retornado.",
                        }
                    ],
                    "missing_scenarios": ["Erro do repositório"],
                    "suggested_fixes": ["Usar fixture do projeto"],
                }
            ]
        )

        self.assertIn(QAGENT_TEST_REVIEW_MEMORY_TAG, comment)
        self.assertIn("src/user.py", comment)
        self.assertIn("Assert genérico demais.", comment)
        self.assertIn("Erro do repositório", comment)

    def test_approved_review_result_does_not_create_finding(self):
        result = GeneratedTestsReviewResult(
            status="APPROVED",
            summary="Testes aderentes.",
        )

        self.assertIsNone(review_result_to_finding("src/user.py", result))


if __name__ == "__main__":
    unittest.main()
