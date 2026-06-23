import io
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import run


class RunPathBootstrapTests(unittest.TestCase):
    def test_inserts_src_path_when_missing(self):
        src_path = str(Path(run.__file__).resolve().parent / "src")
        fake_path = ["C:/tmp/site-packages", "C:/tmp/project"]

        with patch.object(run.sys, "path", fake_path):
            run._ensure_src_on_path()

        self.assertEqual(fake_path[0], src_path)
        self.assertEqual(fake_path.count(src_path), 1)

    def test_does_not_duplicate_src_path_when_already_present(self):
        src_path = str(Path(run.__file__).resolve().parent / "src")
        fake_path = ["C:/tmp/site-packages", src_path, "C:/tmp/project"]

        with patch.object(run.sys, "path", fake_path):
            run._ensure_src_on_path()

        self.assertEqual(fake_path.count(src_path), 1)
        self.assertEqual(fake_path, ["C:/tmp/site-packages", src_path, "C:/tmp/project"])


class RunMainBehaviorTests(unittest.TestCase):
    def test_help_mode_prints_usage_and_exits_cleanly(self):
        out = io.StringIO()

        with patch.object(run.sys, "argv", ["run.py", "--help"]):
            with patch("sys.stdout", new=out):
                code = run.main()

        self.assertEqual(code, 0)
        self.assertIn("Usage:", out.getvalue())
        self.assertIn("python run.py", out.getvalue())

    def test_non_help_mode_delegates_to_cli_main(self):
        fake_cli_main = Mock()
        fake_cli_module = types.ModuleType("bookworm.cli")
        fake_cli_module.main = fake_cli_main

        fake_bookworm_package = types.ModuleType("bookworm")
        fake_bookworm_package.__path__ = []

        with patch.object(run.sys, "argv", ["run.py"]):
            with patch.dict(
                sys.modules,
                {"bookworm": fake_bookworm_package, "bookworm.cli": fake_cli_module},
                clear=False,
            ):
                code = run.main()

        self.assertEqual(code, 0)
        fake_cli_main.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
