"""Fetches the TipToi product catalog directly from the official Ravensburger service page."""

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CATALOG_URL = "https://service.ravensburger.de/tiptoi%C2%AE/tiptoi%C2%AE_Audiodateien"
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 45
REQUEST_TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)
MAX_RETRIES = 4


def _build_session():
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        connect=MAX_RETRIES,
        read=MAX_RETRIES,
        status=MAX_RETRIES,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        }
    )
    return session


def fetch_catalog(on_progress=None, on_warning=None):
    """Scrape the official Ravensburger service page and return a list of products.

    Each product is a dict with keys: title, number, gme.
    `on_progress` is called with (current, total) after each category is processed.
    `on_warning` is called with a warning message when a category cannot be loaded.
    """
    session = _build_session()
    categories = _fetch_categories(session)
    products = []
    for i, category in enumerate(categories):
        try:
            products.extend(_fetch_products_from_category(session, category))
        except requests.RequestException as exc:
            if on_warning:
                on_warning(f"Skipping category '{category['title']}': {exc}")
        if on_progress:
            on_progress(i + 1, len(categories))
    return products


def _fetch_categories(session):
    resp = session.get(CATALOG_URL, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    links = soup.find_all("a", class_="mt-listing-detailed-subpage-title")
    return [
        {"title": a.get("title", ""), "url": urljoin(resp.url, a.get("href", ""))}
        for a in links
    ]


def _sanitize_title(raw_title):
    title = re.sub(r"\s\d{5}.*$", "", raw_title)
    for remove in ("tiptoi®", "Audiodatei", "Audioatei", "\xa0"):
        title = title.replace(remove, " " if remove == "\xa0" else "")
    return title.strip()


def _extract_numbers(raw_title):
    return re.findall(r"\d{5}", raw_title)


def _fetch_products_from_category(session, category):
    numbers = _extract_numbers(category["title"])
    title = _sanitize_title(category["title"])

    resp = session.get(category["url"], timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    gme_links = soup.find_all("a", href=re.compile(r"\.gme", re.IGNORECASE))

    products = []
    for i, link in enumerate(gme_links):
        gme_url = urljoin(resp.url, link.get("href", ""))
        number = numbers[i] if i < len(numbers) else ""
        products.append({
            "title": title,
            "number": number,
            "gme": gme_url,
        })
    return products
