import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import requests

from bookworm.downloader import download_gme


class _FakeResponse:
    def __init__(self, body=b"abc", status_error=None):
        self.headers = {"content-length": str(len(body))}
        self._body = body
        self._status_error = status_error
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        self.closed = True

    def raise_for_status(self):
        if self._status_error is not None:
            raise self._status_error
        return None

    def iter_content(self, chunk_size=8192):
        yield self._body


class DownloadFilenameSafetyTests(unittest.TestCase):
    @patch("bookworm.downloader.requests.get")
    def test_uses_path_basename_not_query_or_fragment(self, mock_get):
        mock_get.return_value = _FakeResponse()
        with tempfile.TemporaryDirectory() as tmp:
            dest = download_gme(
                "https://ravensburger.cloud/files/game%20name.gme?file=evil.txt#frag",
                Path(tmp),
            )
        self.assertEqual(dest.name, "game name.gme")

    @patch("bookworm.downloader.requests.get")
    def test_sanitizes_windows_invalid_characters(self, mock_get):
        mock_get.return_value = _FakeResponse()
        with tempfile.TemporaryDirectory() as tmp:
            dest = download_gme(
                "https://ravensburger.cloud/files/ba%3Cd%3E%3Aname%3F.gme",
                Path(tmp),
            )
        self.assertEqual(dest.name, "ba_d__name_.gme")

    @patch("bookworm.downloader.requests.get")
    def test_fallback_filename_when_path_basename_empty(self, mock_get):
        mock_get.return_value = _FakeResponse()
        with tempfile.TemporaryDirectory() as tmp:
            dest = download_gme("https://ravensburger.cloud/?x=1", Path(tmp))
        self.assertEqual(dest.name, "download.gme")

    @patch("bookworm.downloader.requests.get")
    def test_rejects_non_official_hosts(self, mock_get):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "non-official host"):
                download_gme("https://example.test/files/game.gme", Path(tmp))
        mock_get.assert_not_called()

    @patch("bookworm.downloader.requests.get")
    def test_allows_official_subdomains(self, mock_get):
        mock_get.return_value = _FakeResponse()
        with tempfile.TemporaryDirectory() as tmp:
            dest = download_gme("https://cdn.ravensburger.de/files/game.gme", Path(tmp))
        self.assertEqual(dest.name, "game.gme")

    @patch("bookworm.downloader.requests.get")
    def test_closes_response_when_request_fails(self, mock_get):
        response = _FakeResponse(status_error=requests.HTTPError("boom"))
        mock_get.return_value = response

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(requests.HTTPError):
                download_gme("https://ravensburger.cloud/files/game.gme", Path(tmp))

        self.assertTrue(response.closed)


if __name__ == "__main__":
    unittest.main()


