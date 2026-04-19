import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bookworm.downloader import download_gme


class _FakeResponse:
    def __init__(self, body=b"abc"):
        self.headers = {"content-length": str(len(body))}
        self._body = body

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=8192):
        yield self._body


class DownloadFilenameSafetyTests(unittest.TestCase):
    @patch("bookworm.downloader.requests.get")
    def test_uses_path_basename_not_query_or_fragment(self, mock_get):
        mock_get.return_value = _FakeResponse()
        with tempfile.TemporaryDirectory() as tmp:
            dest = download_gme(
                "https://example.test/files/game%20name.gme?file=evil.txt#frag",
                Path(tmp),
            )
        self.assertEqual(dest.name, "game name.gme")

    @patch("bookworm.downloader.requests.get")
    def test_sanitizes_windows_invalid_characters(self, mock_get):
        mock_get.return_value = _FakeResponse()
        with tempfile.TemporaryDirectory() as tmp:
            dest = download_gme(
                "https://example.test/files/ba%3Cd%3E%3Aname%3F.gme",
                Path(tmp),
            )
        self.assertEqual(dest.name, "ba_d__name_.gme")

    @patch("bookworm.downloader.requests.get")
    def test_fallback_filename_when_path_basename_empty(self, mock_get):
        mock_get.return_value = _FakeResponse()
        with tempfile.TemporaryDirectory() as tmp:
            dest = download_gme("https://example.test/?x=1", Path(tmp))
        self.assertEqual(dest.name, "download.gme")


if __name__ == "__main__":
    unittest.main()
