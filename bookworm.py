"""Run TipToi-Bookworm from repository root without installation."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal, TypedDict

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_INTERRUPTED = 130

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


def _ensure_src_on_path() -> None:
    repo_root = Path(__file__).resolve().parent
    src_dir = repo_root / "src"
    src_path = str(src_dir)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


_ensure_src_on_path()

# When imported as the module named 'bookworm', sys.modules['bookworm'] already
# points here before any bookworm.* submodule imports can resolve (because this
# .py file shadows the src/bookworm/ package).  Temporarily step aside so that
# the package in src/ is found, then restore ourselves.
if __name__ != "__main__":
    _self = sys.modules.pop(__name__, None)
    try:
        from bookworm.catalog import fetch_catalog
        from bookworm.downloader import download_gme, is_official_source
    finally:
        if _self is not None:
            sys.modules[__name__] = _self
    del _self
else:
    from bookworm.catalog import fetch_catalog
    from bookworm.downloader import download_gme, is_official_source


def _normalize_exit_code(code: object) -> int:
    if code is None:
        return EXIT_OK
    if isinstance(code, int):
        return code
    return EXIT_FAILURE


def _load_catalog() -> list:
    print("  Fetching product catalog from Ravensburger \u2026")
    print()

    products = fetch_catalog(
        on_progress=lambda cur, tot: print(
            f"\r  Loading catalog \u2026 {cur}/{tot} categories", end="", flush=True
        ),
        on_warning=lambda msg: print(f"\n  Warning: {msg}"),
    )

    print(f"\r  Catalog loaded \u2014 {len(products)} audio files available.          ")
    print()
    return products


def _search(products: list, term: str) -> list:
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


def _confirm_and_download(chosen: dict) -> bool:
    import requests

    number_info = f" ({chosen['number']})" if chosen["number"] else ""
    print(f"\n  Selected: {chosen['title']}{number_info}")
    print(f"  URL:      {chosen['gme']}")

    if not is_official_source(chosen["gme"]):
        print("  \u26a0 Skipped \u2014 URL is not from an official Ravensburger domain.\n")
        return True

    confirm = input("  Download? [y/N]: ").strip().lower()
    if confirm != CONFIRM_DOWNLOAD:
        print(DOWNLOAD_CANCELLED_MESSAGE)
        return True

    try:
        destination = download_gme(chosen["gme"], Path.cwd())
        print(f"\n  \u2714 Saved to {destination}\n")
    except (requests.RequestException, OSError, ValueError) as exc:
        print(f"\n  \u2718 Download failed: {exc}\n")
    return True


def _run_interactive() -> int:
    import requests

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


def main() -> int:
    _ensure_src_on_path()

    # Keep a safe help mode for uninstalled repo execution.
    if len(sys.argv) > 1 and sys.argv[1] in {"-h", "--help"}:
        print("TipToi-Bookworm repository launcher")
        print("Run the interactive downloader directly from this checkout.")
        print()
        print("Usage:")
        print("  python bookworm.py [--help]")
        print()
        print("Options:")
        print("  -h, --help    Show this help message and exit")
        print()
        print("Exit codes:")
        print("  0   success (including --help)")
        print("  130 interrupted (Ctrl+C)")
        print("  1   launcher or runtime startup failure")
        return EXIT_OK

    try:
        result = _run_interactive()
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
    except SystemExit as exc:
        return _normalize_exit_code(exc.code)

    if isinstance(result, int):
        return result
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())