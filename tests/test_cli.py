import io
import unittest
from unittest.mock import patch

import requests

from support import ensure_src_on_path

ensure_src_on_path()

from bookworm import runtime


class RuntimeExceptionHandlingTests(unittest.TestCase):
    def test_fetch_catalog_request_error_is_handled_friendly(self):
        out = io.StringIO()
        with patch('bookworm.runtime.fetch_catalog', side_effect=requests.RequestException('network down')):
            with patch('sys.stdout', new=out):
                code = runtime.main()

        self.assertEqual(code, 1)
        self.assertIn('Error fetching catalog: network down', out.getvalue())

    def test_fetch_catalog_unexpected_error_propagates(self):
        with patch('bookworm.runtime.fetch_catalog', side_effect=RuntimeError('bug')):
            with self.assertRaises(RuntimeError):
                runtime.main()

    def test_download_value_error_is_handled_friendly(self):
        out = io.StringIO()
        products = [{'title': 'Book', 'number': '12345', 'gme': 'https://ravensburger.cloud/files/book.gme'}]

        with patch('bookworm.runtime.fetch_catalog', return_value=products):
            with patch('bookworm.runtime.is_official_source', return_value=True):
                with patch('bookworm.runtime.download_gme', side_effect=ValueError('bad target')):
                    with patch('builtins.input', side_effect=['book', '1', 'y', 'q']):
                        with patch('sys.stdout', new=out):
                            runtime.main()

        self.assertIn('Download failed: bad target', out.getvalue())

    def test_download_unexpected_error_propagates(self):
        products = [{'title': 'Book', 'number': '12345', 'gme': 'https://ravensburger.cloud/files/book.gme'}]

        with patch('bookworm.runtime.fetch_catalog', return_value=products):
            with patch('bookworm.runtime.is_official_source', return_value=True):
                with patch('bookworm.runtime.download_gme', side_effect=RuntimeError('bug')):
                    with patch('builtins.input', side_effect=['book', '1', 'y']):
                        with self.assertRaises(RuntimeError):
                            runtime.main()


class RuntimeInteractiveLoopTests(unittest.TestCase):
    def test_eof_at_search_prompt_exits_with_bye(self):
        out = io.StringIO()

        with patch('bookworm.runtime.fetch_catalog', return_value=[]):
            with patch('builtins.input', side_effect=EOFError):
                with patch('sys.stdout', new=out):
                    code = runtime.main()

        self.assertEqual(code, 0)
        self.assertIn('Bye!', out.getvalue())

    def test_keyboard_interrupt_at_search_prompt_exits_with_bye(self):
        out = io.StringIO()

        with patch('bookworm.runtime.fetch_catalog', return_value=[]):
            with patch('builtins.input', side_effect=KeyboardInterrupt):
                with patch('sys.stdout', new=out):
                    code = runtime.main()

        self.assertEqual(code, 0)
        self.assertIn('Bye!', out.getvalue())

    def test_keyboard_interrupt_at_selection_exits_gracefully(self):
        out = io.StringIO()
        products = [{'title': 'Book', 'number': '12345', 'gme': 'https://ravensburger.cloud/files/book.gme'}]

        with patch('bookworm.runtime.fetch_catalog', return_value=products):
            with patch('builtins.input', side_effect=['book', KeyboardInterrupt]):
                with patch('sys.stdout', new=out):
                    code = runtime.main()

        self.assertEqual(code, 0)
        self.assertIn('Found 1 result(s):', out.getvalue())
        self.assertIn('Bye!', out.getvalue())

    def test_keyboard_interrupt_at_confirmation_exits_gracefully(self):
        out = io.StringIO()
        products = [{'title': 'Book', 'number': '12345', 'gme': 'https://ravensburger.cloud/files/book.gme'}]

        with patch('bookworm.runtime.fetch_catalog', return_value=products):
            with patch('bookworm.runtime.is_official_source', return_value=True):
                with patch('bookworm.runtime.download_gme') as mock_download:
                    with patch('builtins.input', side_effect=['book', '1', KeyboardInterrupt]):
                        with patch('sys.stdout', new=out):
                            code = runtime.main()

        self.assertEqual(code, 0)
        self.assertIn('Selected: Book (12345)', out.getvalue())
        self.assertIn('Bye!', out.getvalue())
        mock_download.assert_not_called()

    def test_invalid_numeric_selection_prints_message_and_returns_to_search_loop(self):
        out = io.StringIO()
        products = [{'title': 'Book', 'number': '12345', 'gme': 'https://ravensburger.cloud/files/book.gme'}]

        with patch('bookworm.runtime.fetch_catalog', return_value=products):
            with patch('bookworm.runtime.download_gme') as mock_download:
                with patch('builtins.input', side_effect=['book', '999', 'q']):
                    with patch('sys.stdout', new=out):
                        code = runtime.main()

        self.assertEqual(code, 0)
        self.assertIn('Invalid selection.', out.getvalue())
        self.assertIn('Bye!', out.getvalue())
        mock_download.assert_not_called()

    def test_invalid_non_numeric_selection_prints_message_and_returns_to_search_loop(self):
        out = io.StringIO()
        products = [{'title': 'Book', 'number': '12345', 'gme': 'https://ravensburger.cloud/files/book.gme'}]

        with patch('bookworm.runtime.fetch_catalog', return_value=products):
            with patch('bookworm.runtime.download_gme') as mock_download:
                with patch('builtins.input', side_effect=['book', 'banana', 'q']):
                    with patch('sys.stdout', new=out):
                        code = runtime.main()

        self.assertEqual(code, 0)
        self.assertIn('Invalid selection.', out.getvalue())
        self.assertIn('Bye!', out.getvalue())
        mock_download.assert_not_called()

    def test_cancelled_download_prints_message_and_skips_download(self):
        out = io.StringIO()
        products = [{'title': 'Book', 'number': '12345', 'gme': 'https://ravensburger.cloud/files/book.gme'}]

        with patch('bookworm.runtime.fetch_catalog', return_value=products):
            with patch('bookworm.runtime.is_official_source', return_value=True):
                with patch('bookworm.runtime.download_gme') as mock_download:
                    with patch('builtins.input', side_effect=['book', '1', 'n', 'q']):
                        with patch('sys.stdout', new=out):
                            code = runtime.main()

        self.assertEqual(code, 0)
        self.assertIn('Download cancelled.', out.getvalue())
        self.assertIn('Bye!', out.getvalue())
        mock_download.assert_not_called()


if __name__ == '__main__':
    unittest.main()

