import tempfile
import unittest
from pathlib import Path

from src.services.context_builder import RepoContextBuilder


class RepoContextBuilderTests(unittest.TestCase):
    def test_build_includes_existing_tests_and_related_source_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            changed_file = repo / "module" / "calculator.py"
            changed_file.parent.mkdir(parents=True, exist_ok=True)
            changed_file.write_text("def soma(a, b):\n    return a + b\n", encoding="utf-8")

            related_source = repo / "module" / "helpers.py"
            related_source.write_text(
                "from module.calculator import soma\n\n"
                "def soma_segura(a, b):\n"
                "    return soma(a, b)\n",
                encoding="utf-8",
            )

            existing_test = repo / "tests" / "test_calculator.py"
            existing_test.parent.mkdir(parents=True, exist_ok=True)
            existing_test.write_text(
                "from module.calculator import soma\n\n"
                "def test_soma_basica():\n"
                "    assert soma(2, 3) == 5\n",
                encoding="utf-8",
            )

            builder = RepoContextBuilder(str(repo))
            context = builder.build(
                changed_file="module/calculator.py",
                code_content=changed_file.read_text(encoding="utf-8"),
            )

            self.assertEqual(context.file_path, "module/calculator.py")
            self.assertIn("# Testes existentes identificados", context.summary)
            self.assertIn("test_calculator.py", context.summary)
            self.assertIn("test_soma_basica", context.summary)
            self.assertIn("helpers.py", context.summary)
            self.assertIn("soma_segura", context.summary)
            self.assertTrue(
                any(path.endswith("test_calculator.py") for path in context.existing_tests)
            )

    def test_build_reports_when_no_existing_tests_are_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            changed_file = repo / "service" / "payments.py"
            changed_file.parent.mkdir(parents=True, exist_ok=True)
            changed_file.write_text("def processar():\n    return True\n", encoding="utf-8")

            builder = RepoContextBuilder(str(repo))
            context = builder.build(
                changed_file="service/payments.py",
                code_content=changed_file.read_text(encoding="utf-8"),
            )

            self.assertEqual(context.existing_tests, [])
            self.assertIn("Nenhum teste encontrado.", context.summary)
            self.assertIn(
                "Nenhum teste existente identificado no repositório.", context.summary
            )

    def test_build_detects_existing_tests_in_other_languages(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            changed_file = repo / "src" / "OrderService.java"
            changed_file.parent.mkdir(parents=True, exist_ok=True)
            changed_file.write_text(
                "public class OrderService {\n"
                "  public int total(int a, int b) { return a + b; }\n"
                "}\n",
                encoding="utf-8",
            )

            java_test = repo / "src" / "test" / "OrderServiceTest.java"
            java_test.parent.mkdir(parents=True, exist_ok=True)
            java_test.write_text(
                "public class OrderServiceTest {\n"
                "  @org.junit.jupiter.api.Test\n"
                "  void shouldSumTotals() {}\n"
                "}\n",
                encoding="utf-8",
            )

            builder = RepoContextBuilder(str(repo))
            context = builder.build(
                changed_file="src/OrderService.java",
                code_content=changed_file.read_text(encoding="utf-8"),
            )

            self.assertIn("OrderServiceTest.java", context.summary)
            self.assertIn("shouldSumTotals", context.summary)
            self.assertTrue(
                any(path.endswith("OrderServiceTest.java") for path in context.existing_tests)
            )


if __name__ == "__main__":
    unittest.main()
