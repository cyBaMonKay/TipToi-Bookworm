import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from bookworm import cli


class CliExceptionHandlingTests(unittest.TestCase):
    def test_fetch_catalog_request_error_is_handled_friendly(self):
        out = io.StringIO()
        with patch('bookworm.cli.fetch_catalog', side_effect=requests.RequestException('network down')):
            with patch('sys.stdout', new=out):
                with self.assertRaises(SystemExit) as exc_info:
                    cli.main()

        self.assertEqual(exc_info.exception.code, 1)
        self.assertIn('Error fetching catalog: network down', out.getvalue())

    def test_fetch_catalog_unexpected_error_propagates(self):
        with patch('bookworm.cli.fetch_catalog', side_effect=RuntimeError('bug')):
            with self.assertRaises(RuntimeError):
                cli.main()

    def test_download_value_error_is_handled_friendly(self):
        out = io.StringIO()
        products = [{'title': 'Book', 'number': '12345', 'gme': 'https://ravensburger.cloud/files/book.gme'}]

        with patch('bookworm.cli.fetch_catalog', return_value=products):
            with patch('bookworm.cli.is_official_source', return_value=True):
                with patch('bookworm.cli.download_gme', side_effect=ValueError('bad target')):
                    with patch('builtins.input', side_effect=['book', '1', 'y', 'q']):
                        with patch('sys.stdout', new=out):
                            cli.main()

        self.assertIn('Download failed: bad target', out.getvalue())

    def test_download_unexpected_error_propagates(self):
        products = [{'title': 'Book', 'number': '12345', 'gme': 'https://ravensburger.cloud/files/book.gme'}]

        with patch('bookworm.cli.fetch_catalog', return_value=products):
            with patch('bookworm.cli.is_official_source', return_value=True):
                with patch('bookworm.cli.download_gme', side_effect=RuntimeError('bug')):
                    with patch('builtins.input', side_effect=['book', '1', 'y']):
                        with self.assertRaises(RuntimeError):
                            cli.main()


if __name__ == '__main__':
    unittest.main()
