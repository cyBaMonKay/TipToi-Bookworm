"""Fetches the TipToi product catalog directly from the official Ravensburger service page."""

import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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
MAX_WORKERS = 8

_thread_local = threading.local()


def _get_thread_session(created_sessions=None, sessions_lock=None):
    if not hasattr(_thread_local, "session"):
        session = _build_session()
        _thread_local.session = session
        if created_sessions is not None:
            if sessions_lock is None:
                created_sessions.append(session)
            else:
                with sessions_lock:
                    created_sessions.append(session)
    return _thread_local.session


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
    created_sessions = []
    sessions_lock = threading.Lock()
    session = _build_session()
    created_sessions.append(session)

    try:
        categories = _fetch_categories(session)
        total = len(categories)
        products_by_index = {}
        completed = 0
        lock = threading.Lock()

        def _fetch_one(args):
            idx, category = args
            thread_session = _get_thread_session(created_sessions, sessions_lock)
            return idx, _fetch_products_from_category(thread_session, category)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(_fetch_one, (i, cat)): cat
                for i, cat in enumerate(categories)
            }
            for future in as_completed(futures):
                category = futures[future]
                try:
                    idx, prods = future.result()
                    products_by_index[idx] = prods
                except requests.RequestException as exc:
                    if on_warning:
                        on_warning(f"Skipping category '{category['title']}': {exc}")
                with lock:
                    completed += 1
                    if on_progress:
                        on_progress(completed, total)

        products = []
        for i in range(total):
            products.extend(products_by_index.get(i, []))
        return products
    finally:
        if hasattr(_thread_local, "session"):
            delattr(_thread_local, "session")

        with sessions_lock:
            sessions_to_close = list(created_sessions)
            created_sessions.clear()

        for created_session in sessions_to_close:
            created_session.close()


def _fetch_categories(session):
    resp = session.get(CATALOG_URL, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    links = soup.find_all("a", class_="mt-listing-detailed-subpage-title")
    categories = []
    for a in links:
        href = a.get("href", "").strip()
        if not href:
            continue
        url = urljoin(resp.url, href)
        if not url.startswith(("http://", "https://")):
            continue
        categories.append({"title": a.get("title", ""), "url": url})
    return categories


def _sanitize_title(raw_title):
    title = re.sub(r"\s\d{5}.*$", "", raw_title)
    for remove in ("tiptoi\u00ae", "Audiodatei", "Audioatei", "\xa0"):
        title = title.replace(remove, " " if remove == "\xa0" else "")
    return title.strip()


def _extract_numbers(raw_title):
    return re.findall(r"\d{5}", raw_title)


def _unique_number_from_text(*parts):
    numbers = set()
    for part in parts:
        if part:
            numbers.update(re.findall(r"\d{5}", part))
    return next(iter(numbers)) if len(numbers) == 1 else ""


def _extract_number_from_link(link, gme_url):
    href = link.get("href", "")
    link_text = link.get_text(" ", strip=True)
    parent_text = link.parent.get_text(" ", strip=True) if link.parent else ""

    previous = link.previous_sibling
    if previous is None:
        previous_text = ""
    elif hasattr(previous, "get_text") and callable(previous.get_text):
        previous_text = previous.get_text(" ", strip=True)
    else:
        strip_attr = getattr(previous, "strip", None)
        previous_text = strip_attr() if callable(strip_attr) else str(previous).strip()

    return _unique_number_from_text(link_text, href, parent_text, previous_text, gme_url)


def _fetch_products_from_category(session, category):
    title = _sanitize_title(category["title"])

    resp = session.get(category["url"], timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    gme_links = soup.find_all("a", href=re.compile(r"\.gme", re.IGNORECASE))

    products = []
    for link in gme_links:
        gme_url = urljoin(resp.url, link.get("href", ""))
        number = _extract_number_from_link(link, gme_url)
        products.append({
            "title": title,
            "number": number,
            "gme": gme_url,
        })
    return products

