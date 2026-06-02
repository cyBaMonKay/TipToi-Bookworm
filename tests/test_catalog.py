import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from bookworm.catalog import _fetch_categories, _fetch_products_from_category


class _FakeResponse:
    def __init__(self, text, url="https://service.ravensburger.de/cat"):
        self.text = text
        self.url = url

    def raise_for_status(self):
        return None


class _FakeSession:
    def __init__(self, html):
        self._html = html

    def get(self, _url, timeout=None):
        return _FakeResponse(self._html)


class _RaisingSession:
    def __init__(self, exc):
        self._exc = exc

    def get(self, _url, timeout=None):
        raise self._exc


class CatalogNumberMappingTests(unittest.TestCase):
    def test_derives_number_from_each_link_context(self):
        html = """
        <html><body>
          <ul>
            <li><a href="/audio/a.gme">L\u00f6we 12345</a></li>
            <li><a href="/audio/b.gme">Elefant 67890</a></li>
          </ul>
        </body></html>
        """
        session = _FakeSession(html)
        category = {
            "title": "tiptoi\u00ae Tiere 11111 22222 Audiodatei",
            "url": "https://service.ravensburger.de/cat1",
        }

        products = _fetch_products_from_category(session, category)

        self.assertEqual([p["number"] for p in products], ["12345", "67890"])

    def test_uses_empty_when_no_confident_number_in_link_context(self):
        html = """
        <html><body>
          <a href="/audio/story.gme">Geschichte</a>
        </body></html>
        """
        session = _FakeSession(html)
        category = {
            "title": "tiptoi\u00ae Geschichten 12345 67890 Audiodatei",
            "url": "https://service.ravensburger.de/cat2",
        }

        products = _fetch_products_from_category(session, category)

        self.assertEqual(products[0]["number"], "")

    def test_extracts_number_from_previous_sibling_tag_without_crashing(self):
        html = """
        <html><body>
          <p><span>Artikel 54321</span><a href="/audio/story.gme">Geschichte</a></p>
        </body></html>
        """
        session = _FakeSession(html)
        category = {
            "title": "tiptoi\u00ae Geschichten Audiodatei",
            "url": "https://service.ravensburger.de/cat3",
        }

        products = _fetch_products_from_category(session, category)

        self.assertEqual(products[0]["number"], "54321")

    def test_raises_key_error_when_category_title_missing(self):
        session = _FakeSession("<html></html>")

        with self.assertRaises(KeyError):
            _fetch_products_from_category(session, {"url": "https://service.ravensburger.de/cat4"})

    def test_raises_key_error_when_category_url_missing(self):
        session = _FakeSession("<html></html>")

        with self.assertRaises(KeyError):
            _fetch_products_from_category(session, {"title": "tiptoi\u00ae Geschichten Audiodatei"})

    def test_propagates_request_exception_from_category_fetch(self):
        session = _RaisingSession(requests.RequestException("category fetch failed"))
        category = {
            "title": "tiptoi\u00ae Geschichten Audiodatei",
            "url": "https://service.ravensburger.de/cat5",
        }

        with self.assertRaisesRegex(requests.RequestException, "category fetch failed"):
            _fetch_products_from_category(session, category)


class _CloseAwareSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class CatalogSessionCleanupTests(unittest.TestCase):
    def test_closes_all_created_sessions_and_clears_thread_local(self):
        sessions = []

        def _session_factory():
            session = _CloseAwareSession()
            sessions.append(session)
            return session

        with patch("bookworm.catalog._build_session", side_effect=_session_factory):
            with patch("bookworm.catalog._fetch_categories", return_value=[{"title": "Cat", "url": "https://example.test/cat"}]):
                with patch("bookworm.catalog._fetch_products_from_category", return_value=[]):
                    from bookworm import catalog as catalog_module

                    products = catalog_module.fetch_catalog()

        self.assertEqual(products, [])
        self.assertGreaterEqual(len(sessions), 2)
        self.assertTrue(all(session.closed for session in sessions))
        self.assertFalse(hasattr(catalog_module._thread_local, "session"))


class CatalogWarningTests(unittest.TestCase):
    def test_warns_on_request_exception_and_continues_collecting_other_categories(self):
        categories = [
            {"title": "Broken", "url": "https://example.test/broken"},
            {"title": "Working", "url": "https://example.test/working"},
        ]
        progress_updates = []
        warnings = []

        def _fetch_products(_session, category):
            if category["title"] == "Broken":
                raise requests.RequestException("network down")
            return [{"title": "Working", "number": "12345", "gme": "https://example.test/book.gme"}]

        with patch("bookworm.catalog.MAX_WORKERS", 1):
            with patch("bookworm.catalog._fetch_categories", return_value=categories):
                with patch("bookworm.catalog._fetch_products_from_category", side_effect=_fetch_products):
                    from bookworm import catalog as catalog_module

                    products = catalog_module.fetch_catalog(
                        on_progress=lambda current, total: progress_updates.append((current, total)),
                        on_warning=warnings.append,
                    )

        self.assertEqual(
            products,
            [{"title": "Working", "number": "12345", "gme": "https://example.test/book.gme"}],
        )
        self.assertEqual(warnings, ["Skipping category 'Broken': network down"])
        self.assertEqual(progress_updates, [(1, 2), (2, 2)])

    def test_does_not_call_warning_callback_when_all_categories_succeed(self):
        categories = [{"title": "Working", "url": "https://example.test/working"}]
        warnings = []

        with patch("bookworm.catalog.MAX_WORKERS", 1):
            with patch("bookworm.catalog._fetch_categories", return_value=categories):
                with patch(
                    "bookworm.catalog._fetch_products_from_category",
                    return_value=[{"title": "Working", "number": "12345", "gme": "https://example.test/book.gme"}],
                ):
                    from bookworm import catalog as catalog_module

                    products = catalog_module.fetch_catalog(on_warning=warnings.append)

        self.assertEqual(len(products), 1)
        self.assertEqual(warnings, [])


class FetchCategoriesFilterTests(unittest.TestCase):
    def test_extracts_only_valid_listing_links(self):
        html = '''
        <html><body>
          <a class="mt-listing-detailed-subpage-title" href="https://example.test/a" title="Alpha">Alpha</a>
          <a class="mt-listing-detailed-subpage-title" href="mailto:test@example.test" title="Skip">Skip</a>
          <a class="other-class" href="https://example.test/ignored" title="Ignored">Ignored</a>
        </body></html>
        '''

        class _FakeResp:
            text = html
            url = "https://example.test/listing"

            def raise_for_status(self):
                return None

        class _FakeSess:
            def get(self, _url, timeout=None):
                return _FakeResp()

        categories = _fetch_categories(_FakeSess())

        self.assertEqual(
            categories,
            [{"title": "Alpha", "url": "https://example.test/a"}],
        )

    def test_resolves_relative_hrefs_against_listing_url(self):
        html = '''
        <html><body>
          <a class="mt-listing-detailed-subpage-title" href="/tiptoi/audios/cat-a" title="Root Relative">A</a>
          <a class="mt-listing-detailed-subpage-title" href="downloads/cat-b" title="Path Relative">B</a>
        </body></html>
        '''

        class _FakeResp:
            text = html
            url = "https://service.ravensburger.de/tiptoi/listing/index.html"

            def raise_for_status(self):
                return None

        class _FakeSess:
            def get(self, _url, timeout=None):
                return _FakeResp()

        categories = _fetch_categories(_FakeSess())

        self.assertEqual(
            [c["url"] for c in categories],
            [
                "https://service.ravensburger.de/tiptoi/audios/cat-a",
                "https://service.ravensburger.de/tiptoi/listing/downloads/cat-b",
            ],
        )

    def test_skips_missing_or_blank_href_and_keeps_missing_title_as_empty(self):
        html = '''
        <html><body>
          <a class="mt-listing-detailed-subpage-title" href="" title="Empty">Empty</a>
          <a class="mt-listing-detailed-subpage-title" href="   " title="Blank">Blank</a>
          <a class="mt-listing-detailed-subpage-title" title="MissingHref">MissingHref</a>
          <a class="mt-listing-detailed-subpage-title" href="https://example.test/no-title">No Title</a>
        </body></html>
        '''

        class _FakeResp:
            text = html
            url = "https://example.test/listing"

            def raise_for_status(self):
                return None

        class _FakeSess:
            def get(self, _url, timeout=None):
                return _FakeResp()

        categories = _fetch_categories(_FakeSess())

        self.assertEqual(
            categories,
            [{"title": "", "url": "https://example.test/no-title"}],
        )


if __name__ == "__main__":
    unittest.main()
