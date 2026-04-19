import unittest

from bookworm.catalog import _fetch_products_from_category


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


class CatalogNumberMappingTests(unittest.TestCase):
    def test_derives_number_from_each_link_context(self):
        html = """
        <html><body>
          <ul>
            <li><a href="/audio/a.gme">Löwe 12345</a></li>
            <li><a href="/audio/b.gme">Elefant 67890</a></li>
          </ul>
        </body></html>
        """
        session = _FakeSession(html)
        category = {
            "title": "tiptoi® Tiere 11111 22222 Audiodatei",
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
            "title": "tiptoi® Geschichten 12345 67890 Audiodatei",
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
            "title": "tiptoi® Geschichten Audiodatei",
            "url": "https://service.ravensburger.de/cat3",
        }

        products = _fetch_products_from_category(session, category)

        self.assertEqual(products[0]["number"], "54321")


if __name__ == "__main__":
    unittest.main()
