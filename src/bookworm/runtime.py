"""Interactive TipToi-Bookworm runtime for repository execution."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, TypedDict

import requests

from bookworm.catalog import fetch_catalog
from bookworm.downloader import download_gme, is_official_source
from bookworm.types import Product

EXIT_OK = 0
EXIT_FAILURE = 1

QUIT_COMMAND = "q"
BACK_COMMAND = "b"
CONFIRM_DOWNLOAD = "y"

BYE_MESSAGE = "  Bye!"
INVALID_SELECTION_MESSAGE = "  Invalid selection.\n"
DOWNLOAD_CANCELLED_MESSAGE = "  Download cancelled.\n"

BANNER = r"""
 _____ _     _____     _   ___            _
|_   _(_)_ _|_   _|__ (_) | _ ) ___  ___ | |____ __ _____ _ _ _ __
  | | | | '_ \| |/ _ \| | | _ \/ _ \/ _ \| / /\ V  V / _ \ '_| '  \
  |_| |_| .__/|_|\___/|_| |___/\___/\___/|_\_\\_/\_/\___/_| |_|_|_|
        |_|
"""


class QueryPromptResult(TypedDict):
    action: Literal["quit", "continue", "search"]
    query: str


class SelectionParseResult(TypedDict):
    action: Literal["back", "invalid", "selected"]
    index: int | None


def _load_catalog() -> list[Product]:
    print("  Fetching product catalog from Ravensburger …")
    print()

    products = fetch_catalog(
        on_progress=lambda cur, tot: print(
            f"\r  Loading catalog … {cur}/{tot} categories", end="", flush=True
        ),
        on_warning=lambda msg: print(f"\n  Warning: {msg}"),
    )

    print(f"\r  Catalog loaded — {len(products)} audio files available.          ")
    print()
    return products


def _search(products: list[Product], term: str) -> list[Product]:
    term_lower = term.lower()
    return [
        product
        for product in products
        if term_lower in product["title"].lower()
        or term_lower in product.get("number", "").lower()
    ]


def _prompt_query() -> QueryPromptResult:
    query = input(f"  Enter search term (or '{QUIT_COMMAND}' to quit): ").strip()

    if query.lower() == QUIT_COMMAND:
        return {"action": "quit", "query": ""}
    if not query:
        return {"action": "continue", "query": ""}
    return {"action": "search", "query": query}


def _prompt_selection() -> str:
    return input(f"  Select a number to download (or '{BACK_COMMAND}' to go back): ").strip()


def _parse_selection(selection: str, result_count: int) -> SelectionParseResult:
    if selection.lower() == BACK_COMMAND:
        return {"action": "back", "index": None}

    try:
        index = int(selection) - 1
        if index < 0 or index >= result_count:
            raise ValueError
    except ValueError:
        return {"action": "invalid", "index": None}

    return {"action": "selected", "index": index}


def _confirm_and_download(chosen: Product) -> bool:
    number_info = f" ({chosen['number']})" if chosen["number"] else ""
    print(f"\n  Selected: {chosen['title']}{number_info}")
    print(f"  URL:      {chosen['gme']}")

    if not is_official_source(chosen["gme"]):
        print("  ⚠ Skipped — URL is not from an official Ravensburger domain.\n")
        return True

    confirm = input("  Download? [y/N]: ").strip().lower()
    if confirm != CONFIRM_DOWNLOAD:
        print(DOWNLOAD_CANCELLED_MESSAGE)
        return True

    try:
        destination = download_gme(chosen["gme"], Path.cwd())
        print(f"\n  ✔ Saved to {destination}\n")
    except (requests.RequestException, OSError, ValueError) as exc:
        print(f"\n  ✘ Download failed: {exc}\n")
    return True


def main() -> int:
    print(BANNER)

    try:
        products = _load_catalog()
    except (requests.RequestException, OSError) as exc:
        print(f"\n  Error fetching catalog: {exc}")
        return EXIT_FAILURE

    while True:
        try:
            query_result = _prompt_query()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{BYE_MESSAGE}")
            return EXIT_OK

        if query_result["action"] == "quit":
            print(BYE_MESSAGE)
            return EXIT_OK
        if query_result["action"] == "continue":
            continue

        results = _search(products, query_result["query"])

        if not results:
            print("  No results found.\n")
            continue

        print(f"\n  Found {len(results)} result(s):\n")
        for index, item in enumerate(results, 1):
            number_info = f" ({item['number']})" if item["number"] else ""
            print(f"    [{index}] {item['title']}{number_info}")
        print()

        try:
            selection = _prompt_selection()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{BYE_MESSAGE}")
            return EXIT_OK

        selection_result = _parse_selection(selection, len(results))

        if selection_result["action"] == "back":
            print()
            continue

        if selection_result["action"] == "invalid":
            print(INVALID_SELECTION_MESSAGE)
            continue

        try:
            selected_index = selection_result["index"]
            if selected_index is None:
                print(INVALID_SELECTION_MESSAGE)
                continue
            _confirm_and_download(results[selected_index])
        except (EOFError, KeyboardInterrupt):
            print(f"\n{BYE_MESSAGE}")
            return EXIT_OK