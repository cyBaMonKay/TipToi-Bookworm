"""Fetches the TipToi product catalog directly from the official Ravensburger service page."""

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

CATALOG_URL = "https://service.ravensburger.de/tiptoi%C2%AE/tiptoi%C2%AE_Audiodateien"


def fetch_catalog(on_progress=None):
    """Scrape the official Ravensburger service page and return a list of products.

    Each product is a dict with keys: title, number, gme.
    `on_progress` is called with (current, total) after each category is processed.
    """
    categories = _fetch_categories()
    products = []
    for i, category in enumerate(categories):
        products.extend(_fetch_products_from_category(category))
        if on_progress:
            on_progress(i + 1, len(categories))
    return products


def _fetch_categories():
    resp = requests.get(CATALOG_URL, timeout=15)
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


def _fetch_products_from_category(category):
    numbers = _extract_numbers(category["title"])
    title = _sanitize_title(category["title"])

    resp = requests.get(category["url"], timeout=15)
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
