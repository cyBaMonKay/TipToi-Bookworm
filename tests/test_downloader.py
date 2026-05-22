import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import requests

import bookworm.downloader as downloader
from bookworm.downloader import download_gme


class _FakeResponse:
    def __init__(self, body=b"abc", status_error=None, chunks=None, iter_error=None):
        self._body = body
        self._chunks = chunks
        self._status_error = status_error
        self._iter_error = iter_error
        self.closed = False

        if chunks is None:
            content_length = len(body)
        else:
            content_length = sum(len(chunk) for chunk in chunks)
        self.headers = {"content-length": str(content_length)}

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
        if self._chunks is None:
            yield self._body
        else:
            for chunk in self._chunks:
                yield chunk

        if self._iter_error is not None:
            raise self._iter_error


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

    @patch("bookworm.downloader.requests.get")
    def test_skips_keep_alive_empty_chunks_without_error(self, mock_get):
        mock_get.return_value = _FakeResponse(chunks=[b"ab", b"", b"c", b""])

        with tempfile.TemporaryDirectory() as tmp:
            dest = download_gme("https://ravensburger.cloud/files/game.gme", Path(tmp))
            self.assertEqual(dest.read_bytes(), b"abc")

    @patch("bookworm.downloader.requests.get")
    def test_interrupted_stream_never_leaves_final_or_temp_file(self, mock_get):
        response = _FakeResponse(
            chunks=[b"abc"],
            iter_error=requests.ConnectionError("stream interrupted"),
        )
        mock_get.return_value = response

        with tempfile.TemporaryDirectory() as tmp:
            target_dir = Path(tmp)
            expected_dest = target_dir / "game.gme"

            with self.assertRaisesRegex(requests.ConnectionError, "interrupted"):
                download_gme("https://ravensburger.cloud/files/game.gme", target_dir)

            self.assertFalse(expected_dest.exists())
            self.assertEqual(list(target_dir.glob(".game.gme.*.part")), [])

        self.assertTrue(response.closed)

    @patch("bookworm.downloader.requests.get")
    def test_successful_download_uses_atomic_replace_into_final_name(self, mock_get):
        mock_get.return_value = _FakeResponse(chunks=[b"ab", b"cd"])

        with tempfile.TemporaryDirectory() as tmp:
            with patch("bookworm.downloader.os.replace", wraps=downloader.os.replace) as mock_replace:
                dest = download_gme("https://ravensburger.cloud/files/game.gme", Path(tmp))

            self.assertTrue(dest.exists())
            self.assertEqual(dest.read_bytes(), b"abcd")
            self.assertEqual(mock_replace.call_count, 1)

            source_tmp, destination = mock_replace.call_args.args
            self.assertEqual(Path(destination), dest)
            self.assertTrue(Path(source_tmp).name.startswith(".game.gme."))
            self.assertEqual(Path(source_tmp).suffix, ".part")
            self.assertFalse(Path(source_tmp).exists())

    @patch("bookworm.downloader.os.fdopen", side_effect=OSError("disk full"))
    @patch("bookworm.downloader.requests.get")
    def test_raises_filesystem_error_when_write_fails(self, mock_get, mock_fdopen):
        mock_get.return_value = _FakeResponse()

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(OSError, "disk full"):
                download_gme("https://ravensburger.cloud/files/game.gme", Path(tmp))

        mock_fdopen.assert_called_once()

    @patch("bookworm.downloader.requests.get", side_effect=requests.Timeout("timed out"))
    def test_raises_network_error_when_request_fails_before_response(self, mock_get):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(requests.Timeout, "timed out"):
                download_gme("https://ravensburger.cloud/files/game.gme", Path(tmp))

        mock_get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
