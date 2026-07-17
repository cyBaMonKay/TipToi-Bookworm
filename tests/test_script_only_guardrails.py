import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class ScriptOnlyGuardrailTests(unittest.TestCase):
    def test_cli_module_is_not_present(self):
        cli_module = REPO_ROOT / "src" / "bookworm" / "cli.py"
        self.assertFalse(cli_module.exists(), f"Unexpected CLI module present: {cli_module}")

    def test_pyproject_does_not_reintroduce_console_entrypoints(self):
        pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertNotIn("[project.scripts]", pyproject_text)
        self.assertNotIn("console_scripts", pyproject_text)
        self.assertNotIn("bookworm.cli", pyproject_text)
        self.assertIn('entrypoint = "python run.py"', pyproject_text)


if __name__ == "__main__":
    unittest.main()