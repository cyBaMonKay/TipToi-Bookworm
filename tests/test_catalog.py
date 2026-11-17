import unittest
from unittest.mock import patch

import requests

from support import FakeHtmlSession, RaisingSession, ensure_src_on_path

ensure_src_on_path()

from bookworm.catalog import (
    _fetch_categories,
    _fetch_products_from_category,
    _get_previous_sibling_text,
    _unique_number_or_empty,
)


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
        session = FakeHtmlSession(html)
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
        session = FakeHtmlSession(html)
        category = {
            "title": "tiptoi\u00ae Geschichten 12345 67890 Audiodatei",
            "url": "https://service.ravensburger.de/cat2",
        }

        products = _fetch_products_from_category(session, category)

        self.assertEqual(products[0]["number"], "")

    def test_uses_unique_page_title_number_when_link_has_no_number(self):
        html = """
        <html><body>
          <a href="/audio/story.gme"><img src="cover.png"></a>
        </body></html>
        """
        session = FakeHtmlSession(html)
        category = {
            "title": "tiptoi\u00ae Audiodatei Story 00758",
            "url": "https://service.ravensburger.de/story",
        }

        products = _fetch_products_from_category(session, category)

        self.assertEqual(products[0]["number"], "00758")

    def test_prefers_confident_link_number_over_unique_page_title_number(self):
        html = """
        <html><body>
          <a href="/audio/story-67890.gme">Geschichte 67890</a>
        </body></html>
        """
        session = FakeHtmlSession(html)
        category = {
            "title": "tiptoi\u00ae Audiodatei Story 12345",
            "url": "https://service.ravensburger.de/story",
        }

        products = _fetch_products_from_category(session, category)

        self.assertEqual(products[0]["number"], "67890")

    def test_prefers_unique_surrounding_context_number_over_page_title_number(self):
        products = _fetch_products_from_category(
            FakeHtmlSession(
                '<p>Artikel 54321 '
                '<a href="/audio/story.gme"><img src="cover.png"></a></p>'
            ),
            {
                "title": "tiptoi\u00ae Audiodatei Story 12345",
                "url": "https://service.ravensburger.de/story",
            },
        )

        self.assertEqual(products[0]["number"], "54321")

    def test_prefers_explicit_link_numbers_over_surrounding_numbers(self):
        for number in ("00001", "00758", "54321", "99999"):
            for anchor in (
                f'<a href="/audio/story.gme">Story {number}</a>',
                f'<a href="/audio/story-{number}.gme"><img src="cover.png"></a>',
                f'<a href="/audio/story-{number}.gme">Story {number}</a>',
            ):
                with self.subTest(number=number, anchor=anchor):
                    products = _fetch_products_from_category(
                        FakeHtmlSession(f"<p>Artikel 12345 {anchor}</p>"),
                        {"title": "Story 12345", "url": "https://service.ravensburger.de/story"},
                    )

                    self.assertEqual(products[0]["number"], number)

    def test_does_not_replace_conflicting_link_numbers_with_context_or_title(self):
        for anchor in (
            '<a href="/audio/story.gme">Story 12345 / 67890</a>',
            '<a href="/audio/story-12345-67890.gme"><img src="cover.png"></a>',
            '<a href="/audio/story-12345.gme">Story 67890</a>',
        ):
            with self.subTest(anchor=anchor):
                products = _fetch_products_from_category(
                    FakeHtmlSession(f"<p>Artikel 12345 {anchor}</p>"),
                    {"title": "Story 12345", "url": "https://service.ravensburger.de/story"},
                )

                self.assertEqual(products[0]["number"], "")

    def test_does_not_replace_conflicting_context_with_title_number(self):
        products = _fetch_products_from_category(
            FakeHtmlSession(
                '<p>Artikel 12345 <span>67890</span>'
                '<a href="/audio/story.gme"><img src="cover.png"></a></p>'
            ),
            {"title": "Story 12345", "url": "https://service.ravensburger.de/story"},
        )

        self.assertEqual(products[0]["number"], "")

    def test_maps_explicit_numbers_in_shared_parent_independently(self):
        products = _fetch_products_from_category(
            FakeHtmlSession(
                '<div><a href="/audio/first.gme">First 12345</a>'
                '<a href="/audio/second.gme">Second 67890</a></div>'
            ),
            {"title": "Stories 12345 67890", "url": "https://service.ravensburger.de/stories"},
        )

        self.assertEqual([p["number"] for p in products], ["12345", "67890"])

    def test_does_not_assign_other_products_number_to_unnumbered_download(self):
        for html, first_number in (
            (
                '<div><a href="/audio/first.gme">First 12345</a>'
                '<a href="/audio/second.gme"><img src="cover.png"></a></div>',
                "12345",
            ),
            (
                '<div><p><a href="/audio/first.gme">First 12345</a></p>'
                '<a href="/audio/second.gme"><img src="cover.png"></a></div>',
                "12345",
            ),
            (
                '<div><a href="/audio/first-67890.gme"><img src="first.png"></a></div>'
                '<div><a href="/audio/second.gme"><img src="second.png"></a></div>',
                "67890",
            ),
        ):
            with self.subTest(html=html):
                products = _fetch_products_from_category(
                    FakeHtmlSession(html),
                    {"title": "Stories 12345", "url": "https://service.ravensburger.de/stories"},
                )

                self.assertEqual([p["number"] for p in products], [first_number, ""])

    def test_title_fallback_requires_one_distinct_download(self):
        for second_href, expected in (
            ("/audio/first.gme", ["00758", "00758"]),
            ("/audio/second.gme", ["", ""]),
        ):
            with self.subTest(second_href=second_href):
                products = _fetch_products_from_category(
                    FakeHtmlSession(
                        '<a href="/audio/first.gme"><img src="cover.png"></a>'
                        f'<a href="{second_href}">Download</a>'
                    ),
                    {"title": "Story 00758 00758", "url": "https://service.ravensburger.de/story"},
                )

                self.assertEqual([p["number"] for p in products], expected)

    def test_keeps_shared_context_for_repeated_links_to_same_download(self):
        products = _fetch_products_from_category(
            FakeHtmlSession(
                '<div>Artikel 54321 <a href="/audio/story.gme">Download</a>'
                '<a href="https://service.ravensburger.de/audio/story.gme">Download again</a></div>'
            ),
            {"title": "Story", "url": "https://service.ravensburger.de/story"},
        )

        self.assertEqual([p["number"] for p in products], ["54321", "54321"])

    def test_does_not_extract_article_numbers_from_longer_digit_sequences(self):
        for title, expected in (("Story 00758", "00758"), ("Story 123456", "")):
            with self.subTest(title=title):
                products = _fetch_products_from_category(
                    FakeHtmlSession('<a href="/audio/story-123456.gme">Download</a>'),
                    {"title": title, "url": "https://service.ravensburger.de/story"},
                )

                self.assertEqual(products[0]["number"], expected)

    def test_extracts_number_from_previous_sibling_tag_without_crashing(self):
        html = """
        <html><body>
          <p><span>Artikel 54321</span><a href="/audio/story.gme">Geschichte</a></p>
        </body></html>
        """
        session = FakeHtmlSession(html)
        category = {
            "title": "tiptoi\u00ae Geschichten Audiodatei",
            "url": "https://service.ravensburger.de/cat3",
        }

        products = _fetch_products_from_category(session, category)

        self.assertEqual(products[0]["number"], "54321")

    def test_raises_key_error_when_category_title_missing(self):
        session = FakeHtmlSession("<html></html>")

        with self.assertRaises(KeyError):
            _fetch_products_from_category(session, {"url": "https://service.ravensburger.de/cat4"})

    def test_raises_key_error_when_category_url_missing(self):
        session = FakeHtmlSession("<html></html>")

        with self.assertRaises(KeyError):
            _fetch_products_from_category(session, {"title": "tiptoi\u00ae Geschichten Audiodatei"})

    def test_propagates_request_exception_from_category_fetch(self):
        session = RaisingSession(requests.RequestException("category fetch failed"))
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
        # A single category failure should emit a warning and not abort remaining work.
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

        session = FakeHtmlSession(html, url="https://example.test/listing")

        categories = _fetch_categories(session)

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

        session = FakeHtmlSession(html, url="https://service.ravensburger.de/tiptoi/listing/index.html")

        categories = _fetch_categories(session)

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

        session = FakeHtmlSession(html, url="https://example.test/listing")

        categories = _fetch_categories(session)

        self.assertEqual(
            categories,
            [{"title": "", "url": "https://example.test/no-title"}],
        )


class GetPreviousSiblingTextTests(unittest.TestCase):
    def test_returns_empty_string_for_none(self):
        self.assertEqual(_get_previous_sibling_text(None), "")

    def test_returns_get_text_result_for_tag_node(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup("<p><span>hello world</span><a></a></p>", "html.parser")
        a_tag = soup.find("a")
        sibling = a_tag.previous_sibling  # the <span> tag
        self.assertEqual(_get_previous_sibling_text(sibling), "hello world")

    def test_returns_stripped_string_for_navigable_string(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup("<p>  plain text  <a></a></p>", "html.parser")
        a_tag = soup.find("a")
        sibling = a_tag.previous_sibling  # NavigableString
        self.assertEqual(_get_previous_sibling_text(sibling), "plain text")

    def test_falls_back_to_str_strip_for_arbitrary_object_without_strip(self):
        class _NoStrip:
            def __str__(self):
                return "  raw  "

        self.assertEqual(_get_previous_sibling_text(_NoStrip()), "raw")

    def test_calls_strip_when_available_and_not_get_text(self):
        class _HasStrip:
            def strip(self):
                return "stripped"

        self.assertEqual(_get_previous_sibling_text(_HasStrip()), "stripped")


class UniqueNumberOrEmptyTests(unittest.TestCase):
    def test_returns_number_when_exactly_one_unique_number_across_parts(self):
        self.assertEqual(_unique_number_or_empty("Artikel 12345", "12345"), "12345")

    def test_returns_empty_when_no_numbers_found(self):
        self.assertEqual(_unique_number_or_empty("no digits", "also none"), "")

    def test_returns_empty_when_multiple_distinct_numbers_found(self):
        self.assertEqual(_unique_number_or_empty("12345", "67890"), "")

    def test_returns_empty_when_no_parts_given(self):
        self.assertEqual(_unique_number_or_empty(), "")

    def test_ignores_none_and_empty_string_parts(self):
        self.assertEqual(_unique_number_or_empty(None, "", "54321"), "54321")

    def test_treats_same_number_in_multiple_parts_as_one_unique_number(self):
        self.assertEqual(_unique_number_or_empty("54321", "54321", "54321"), "54321")


class FetchCategoriesDiagnosticsTests(unittest.TestCase):
    def _make_fake_session(self, html, url="https://example.test/listing"):
        return FakeHtmlSession(html, url=url)

    def test_warns_when_no_category_anchors_found(self):
        session = self._make_fake_session("<html><body><p>No links here.</p></body></html>")
        warnings = []

        categories = _fetch_categories(session, on_warning=warnings.append)

        self.assertEqual(categories, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("No category anchors found", warnings[0])

    def test_does_not_warn_when_categories_are_present(self):
        html = '''<html><body>
          <a class="mt-listing-detailed-subpage-title" href="https://example.test/a" title="Alpha">A</a>
        </body></html>'''
        session = self._make_fake_session(html)
        warnings = []

        categories = _fetch_categories(session, on_warning=warnings.append)

        self.assertEqual(len(categories), 1)
        self.assertEqual(warnings, [])

    def test_does_not_raise_when_no_warning_callback_provided(self):
        session = self._make_fake_session("<html><body></body></html>")
        # Should not raise even without a callback
        categories = _fetch_categories(session)
        self.assertEqual(categories, [])


if __name__ == "__main__":
    unittest.main()

