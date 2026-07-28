import importlib.util
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import requests


def _load_bookworm_script():
    """Load bookworm.py by file path to avoid collision with the src/bookworm/ package."""
    repo_root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("bookworm_script", repo_root / "bookworm.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["bookworm_script"] = mod
    spec.loader.exec_module(mod)
    return mod


bw = _load_bookworm_script()


class BookwormPathBootstrapTests(unittest.TestCase):
    def test_inserts_src_path_when_missing(self):
        src_path = str(Path(bw.__file__).resolve().parent / "src")
        fake_path = ["C:/tmp/site-packages", "C:/tmp/project"]

        with patch.object(bw.sys, "path", fake_path):
            bw._ensure_src_on_path()

        self.assertEqual(fake_path[0], src_path)
        self.assertEqual(fake_path.count(src_path), 1)

    def test_does_not_duplicate_src_path_when_already_present(self):
        src_path = str(Path(bw.__file__).resolve().parent / "src")
        fake_path = ["C:/tmp/site-packages", src_path, "C:/tmp/project"]

        with patch.object(bw.sys, "path", fake_path):
            bw._ensure_src_on_path()

        self.assertEqual(fake_path.count(src_path), 1)
        self.assertEqual(fake_path, ["C:/tmp/site-packages", src_path, "C:/tmp/project"])


class BookwormMainBehaviorTests(unittest.TestCase):
    def test_help_mode_prints_usage_and_exits_cleanly(self):
        out = io.StringIO()

        with patch.object(bw.sys, "argv", ["bookworm.py", "--help"]):
            with patch("sys.stdout", new=out):
                code = bw.main()

        self.assertEqual(code, 0)
        self.assertIn("Usage:", out.getvalue())
        self.assertIn("python bookworm.py [--help]", out.getvalue())
        self.assertIn("Exit codes:", out.getvalue())

    def test_non_help_mode_delegates_to_run_interactive(self):
        with patch.object(bw.sys, "argv", ["bookworm.py"]):
            with patch.object(bw, "_run_interactive", return_value=0) as mock_run:
                code = bw.main()

        self.assertEqual(code, 0)
        mock_run.assert_called_once_with()

    def test_non_help_mode_returns_integer_from_run_interactive(self):
        with patch.object(bw.sys, "argv", ["bookworm.py"]):
            with patch.object(bw, "_run_interactive", return_value=7) as mock_run:
                code = bw.main()

        self.assertEqual(code, 7)
        mock_run.assert_called_once_with()

    def test_non_help_mode_normalizes_system_exit_code(self):
        with patch.object(bw.sys, "argv", ["bookworm.py"]):
            with patch.object(bw, "_run_interactive", side_effect=SystemExit("boom")):
                code = bw.main()

        self.assertEqual(code, 1)

    def test_non_help_mode_returns_interrupted_code_for_keyboard_interrupt(self):
        with patch.object(bw.sys, "argv", ["bookworm.py"]):
            with patch.object(bw, "_run_interactive", side_effect=KeyboardInterrupt):
                code = bw.main()

        self.assertEqual(code, bw.EXIT_INTERRUPTED)


class BookwormExceptionHandlingTests(unittest.TestCase):
    def test_fetch_catalog_request_error_is_handled_friendly(self):
        out = io.StringIO()
        with patch.object(bw, "_load_catalog", side_effect=requests.RequestException("network down")):
            with patch("sys.stdout", new=out):
                code = bw._run_interactive()

        self.assertEqual(code, 1)
        self.assertIn("Error fetching catalog: network down", out.getvalue())

    def test_fetch_catalog_unexpected_error_propagates(self):
        with patch.object(bw, "_load_catalog", side_effect=RuntimeError("bug")):
            with self.assertRaises(RuntimeError):
                bw._run_interactive()

    def test_download_value_error_is_handled_friendly(self):
        out = io.StringIO()
        products = [{"title": "Book", "number": "12345", "gme": "https://ravensburger.cloud/files/book.gme"}]

        with patch.object(bw, "_load_catalog", return_value=products):
            with patch.object(bw, "is_official_source", return_value=True):
                with patch.object(bw, "download_gme", side_effect=ValueError("bad target")):
                    with patch("builtins.input", side_effect=["book", "1", "y", "q"]):
                        with patch("sys.stdout", new=out):
                            bw._run_interactive()

        self.assertIn("Download failed: bad target", out.getvalue())

    def test_download_unexpected_error_propagates(self):
        products = [{"title": "Book", "number": "12345", "gme": "https://ravensburger.cloud/files/book.gme"}]

        with patch.object(bw, "_load_catalog", return_value=products):
            with patch.object(bw, "is_official_source", return_value=True):
                with patch.object(bw, "download_gme", side_effect=RuntimeError("bug")):
                    with patch("builtins.input", side_effect=["book", "1", "y"]):
                        with self.assertRaises(RuntimeError):
                            bw._run_interactive()


class BookwormInteractiveLoopTests(unittest.TestCase):
    def test_quit_command_exits_cleanly(self):
        out = io.StringIO()

        with patch.object(bw, "_load_catalog", return_value=[]):
            with patch("builtins.input", side_effect=["q"]):
                with patch("sys.stdout", new=out):
                    code = bw._run_interactive()

        self.assertEqual(code, 0)
        self.assertIn("Bye!", out.getvalue())

    def test_eof_at_search_prompt_exits_with_bye(self):
        out = io.StringIO()

        with patch.object(bw, "_load_catalog", return_value=[]):
            with patch("builtins.input", side_effect=EOFError):
                with patch("sys.stdout", new=out):
                    code = bw._run_interactive()

        self.assertEqual(code, 0)
        self.assertIn("Bye!", out.getvalue())

    def test_keyboard_interrupt_at_search_prompt_exits_with_bye(self):
        out = io.StringIO()

        with patch.object(bw, "_load_catalog", return_value=[]):
            with patch("builtins.input", side_effect=KeyboardInterrupt):
                with patch("sys.stdout", new=out):
                    code = bw._run_interactive()

        self.assertEqual(code, 0)
        self.assertIn("Bye!", out.getvalue())

    def test_keyboard_interrupt_at_selection_exits_gracefully(self):
        out = io.StringIO()
        products = [{"title": "Book", "number": "12345", "gme": "https://ravensburger.cloud/files/book.gme"}]

        with patch.object(bw, "_load_catalog", return_value=products):
            with patch("builtins.input", side_effect=["book", KeyboardInterrupt]):
                with patch("sys.stdout", new=out):
                    code = bw._run_interactive()

        self.assertEqual(code, 0)
        self.assertIn("Found 1 result(s):", out.getvalue())
        self.assertIn("Bye!", out.getvalue())

    def test_keyboard_interrupt_at_confirmation_exits_gracefully(self):
        out = io.StringIO()
        products = [{"title": "Book", "number": "12345", "gme": "https://ravensburger.cloud/files/book.gme"}]

        with patch.object(bw, "_load_catalog", return_value=products):
            with patch.object(bw, "is_official_source", return_value=True):
                with patch.object(bw, "download_gme") as mock_download:
                    with patch("builtins.input", side_effect=["book", "1", KeyboardInterrupt]):
                        with patch("sys.stdout", new=out):
                            code = bw._run_interactive()

        self.assertEqual(code, 0)
        self.assertIn("Selected: Book (12345)", out.getvalue())
        self.assertIn("Bye!", out.getvalue())
        mock_download.assert_not_called()

    def test_invalid_numeric_selection_prints_message_and_returns_to_search_loop(self):
        out = io.StringIO()
        products = [{"title": "Book", "number": "12345", "gme": "https://ravensburger.cloud/files/book.gme"}]

        with patch.object(bw, "_load_catalog", return_value=products):
            with patch.object(bw, "download_gme") as mock_download:
                with patch("builtins.input", side_effect=["book", "999", "q"]):
                    with patch("sys.stdout", new=out):
                        code = bw._run_interactive()

        self.assertEqual(code, 0)
        self.assertIn("Invalid selection.", out.getvalue())
        self.assertIn("Bye!", out.getvalue())
        mock_download.assert_not_called()

    def test_invalid_non_numeric_selection_prints_message_and_returns_to_search_loop(self):
        out = io.StringIO()
        products = [{"title": "Book", "number": "12345", "gme": "https://ravensburger.cloud/files/book.gme"}]

        with patch.object(bw, "_load_catalog", return_value=products):
            with patch.object(bw, "download_gme") as mock_download:
                with patch("builtins.input", side_effect=["book", "banana", "q"]):
                    with patch("sys.stdout", new=out):
                        code = bw._run_interactive()

        self.assertEqual(code, 0)
        self.assertIn("Invalid selection.", out.getvalue())
        self.assertIn("Bye!", out.getvalue())
        mock_download.assert_not_called()

    def test_cancelled_download_prints_message_and_skips_download(self):
        out = io.StringIO()
        products = [{"title": "Book", "number": "12345", "gme": "https://ravensburger.cloud/files/book.gme"}]

        with patch.object(bw, "_load_catalog", return_value=products):
            with patch.object(bw, "is_official_source", return_value=True):
                with patch.object(bw, "download_gme") as mock_download:
                    with patch("builtins.input", side_effect=["book", "1", "n", "q"]):
                        with patch("sys.stdout", new=out):
                            code = bw._run_interactive()

        self.assertEqual(code, 0)
        self.assertIn("Download cancelled.", out.getvalue())
        self.assertIn("Bye!", out.getvalue())
        mock_download.assert_not_called()


if __name__ == "__main__":
    unittest.main()