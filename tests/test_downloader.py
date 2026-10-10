import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from support import FakeDownloadResponse, ensure_src_on_path

ensure_src_on_path()

import bookworm.downloader as downloader
from bookworm.downloader import download_gme, is_official_source


class DownloadFilenameSafetyTests(unittest.TestCase):
    def test_official_source_host_validation_matrix(self):
        cases = [
            ("https://ravensburger.cloud/files/game.gme", True, "exact host match"),
            ("https://cdn.ravensburger.de/files/game.gme", True, "subdomain match"),
            ("https://RAVENSBURGER.CLOUD/files/game.gme", True, "uppercase host handling"),
            ("https://ravensburger.cloud./files/game.gme", False, "trailing-dot host behavior"),
            ("https://evilravensburger.cloud/files/game.gme", False, "disallowed lookalike"),
            ("not a url", False, "malformed URL"),
            ("https://", False, "malformed URL with empty host"),
        ]

        for url, expected, scenario in cases:
            with self.subTest(scenario=scenario, url=url):
                self.assertEqual(is_official_source(url), expected)

    @patch("bookworm.downloader.requests.get")
    def test_uses_path_basename_not_query_or_fragment(self, mock_get):
        mock_get.return_value = FakeDownloadResponse()
        with tempfile.TemporaryDirectory() as tmp:
            dest = download_gme(
                "https://ravensburger.cloud/files/game%20name.gme?file=evil.txt#frag",
                Path(tmp),
            )
        self.assertEqual(dest.name, "game name.gme")

    @patch("bookworm.downloader.requests.get")
    def test_sanitizes_windows_invalid_characters(self, mock_get):
        mock_get.return_value = FakeDownloadResponse()
        with tempfile.TemporaryDirectory() as tmp:
            dest = download_gme(
                "https://ravensburger.cloud/files/ba%3Cd%3E%3Aname%3F.gme",
                Path(tmp),
            )
        self.assertEqual(dest.name, "ba_d__name_.gme")

    @patch("bookworm.downloader.requests.get")
    def test_fallback_filename_when_path_basename_empty(self, mock_get):
        mock_get.return_value = FakeDownloadResponse()
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
    def test_rejects_non_gme_paths_on_official_hosts(self, mock_get):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, r"expected a \.gme file"):
                download_gme("https://ravensburger.cloud/files/game.txt", Path(tmp))
        mock_get.assert_not_called()

    @patch("bookworm.downloader.requests.get")
    def test_allows_official_subdomains(self, mock_get):
        mock_get.return_value = FakeDownloadResponse()
        with tempfile.TemporaryDirectory() as tmp:
            dest = download_gme("https://cdn.ravensburger.de/files/game.gme", Path(tmp))
        self.assertEqual(dest.name, "game.gme")

    @patch("bookworm.downloader.requests.get")
    def test_closes_response_when_request_fails(self, mock_get):
        response = FakeDownloadResponse(status_error=requests.HTTPError("boom"))
        mock_get.return_value = response

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(requests.HTTPError):
                download_gme("https://ravensburger.cloud/files/game.gme", Path(tmp))

        self.assertTrue(response.closed)

    @patch("bookworm.downloader.requests.get")
    def test_skips_keep_alive_empty_chunks_without_error(self, mock_get):
        mock_get.return_value = FakeDownloadResponse(chunks=[b"ab", b"", b"c", b""])

        with tempfile.TemporaryDirectory() as tmp:
            dest = download_gme("https://ravensburger.cloud/files/game.gme", Path(tmp))
            self.assertEqual(dest.read_bytes(), b"abc")

    @patch("bookworm.downloader.tqdm")
    @patch("bookworm.downloader.requests.get")
    def test_uses_elapsed_and_remaining_time_progress_format(self, mock_get, mock_tqdm):
        mock_get.return_value = FakeDownloadResponse(chunks=[b"ab", b"c"])
        mock_tqdm.return_value.__enter__.return_value = Mock()

        with tempfile.TemporaryDirectory() as tmp:
            download_gme("https://ravensburger.cloud/files/game.gme", Path(tmp))

        self.assertEqual(
            mock_tqdm.call_args.kwargs["bar_format"],
            downloader.PROGRESS_BAR_FORMAT,
        )
        self.assertIn("{remaining}", downloader.PROGRESS_BAR_FORMAT)

    @patch("bookworm.downloader.requests.get")
    def test_interrupted_stream_never_leaves_final_or_temp_file(self, mock_get):
        # Simulate mid-stream failure and assert cleanup of both final and temp artifacts.
        response = FakeDownloadResponse(
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
        # Verify we write via temp file and publish with a single atomic replace.
        mock_get.return_value = FakeDownloadResponse(chunks=[b"ab", b"cd"])

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
        mock_get.return_value = FakeDownloadResponse()

        with tempfile.TemporaryDirectory() as tmp:
            target_dir = Path(tmp)
            with self.assertRaisesRegex(OSError, "disk full"):
                download_gme("https://ravensburger.cloud/files/game.gme", target_dir)

            self.assertFalse((target_dir / "game.gme").exists())
            self.assertEqual(list(target_dir.glob(".game.gme.*.part")), [])

        mock_fdopen.assert_called_once()

    @patch("bookworm.downloader.os.replace", side_effect=OSError("replace failed"))
    @patch("bookworm.downloader.requests.get")
    def test_replace_failure_removes_partial_temp_file(self, mock_get, mock_replace):
        mock_get.return_value = FakeDownloadResponse(chunks=[b"abc"])

        with tempfile.TemporaryDirectory() as tmp:
            target_dir = Path(tmp)
            with self.assertRaisesRegex(OSError, "replace failed"):
                download_gme("https://ravensburger.cloud/files/game.gme", target_dir)

            self.assertFalse((target_dir / "game.gme").exists())
            self.assertEqual(list(target_dir.glob(".game.gme.*.part")), [])

        mock_replace.assert_called_once()

    @patch("bookworm.downloader.requests.get", side_effect=requests.Timeout("timed out"))
    def test_raises_network_error_when_request_fails_before_response(self, mock_get):
        with tempfile.TemporaryDirectory() as tmp:
            target_dir = Path(tmp)
            with self.assertRaisesRegex(requests.Timeout, "timed out"):
                download_gme("https://ravensburger.cloud/files/game.gme", target_dir)

            self.assertFalse((target_dir / "game.gme").exists())
            self.assertEqual(list(target_dir.glob(".game.gme.*.part")), [])

        mock_get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
