"""TipToi-Bookworm CLI — search and download TipToi audio files from Ravensburger."""

import sys
from pathlib import Path

from bookworm.catalog import fetch_catalog
from bookworm.downloader import download_gme, is_official_source

BANNER = r"""
 _____ _     _____     _   ___            _
|_   _(_)_ _|_   _|__ (_) | _ ) ___  ___ | |____ __ _____ _ _ _ __
  | | | | '_ \| |/ _ \| | | _ \/ _ \/ _ \| / /\ V  V / _ \ '_| '  \
  |_| |_| .__/|_|\___/|_| |___/\___/\___/|_\_\ \_/\_/\___/_| |_|_|_|
        |_|
"""
def _search(products: list[dict], term: str) -> list[dict]:
    term_lower = term.lower()
    return [
        p for p in products
        if term_lower in p["title"].lower() or term_lower in p.get("number", "").lower()
    ]


def main():
    print(BANNER)
    print("  Fetching product catalog from Ravensburger …")
    print()

    try:
        products = fetch_catalog(
            on_progress=lambda cur, tot: print(
                f"\r  Loading catalog … {cur}/{tot} categories", end="", flush=True
            ),
            on_warning=lambda msg: print(f"\n  Warning: {msg}"),
        )
    except Exception as exc:
        print(f"\n  Error fetching catalog: {exc}")
        sys.exit(1)

    print(f"\r  Catalog loaded — {len(products)} audio files available.          ")
    print()

    while True:
        try:
            query = input("  Enter search term (or 'q' to quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Bye!")
            break

        if query.lower() == "q":
            print("  Bye!")
            break
        if not query:
            continue

        results = _search(products, query)

        if not results:
            print("  No results found.\n")
            continue

        print(f"\n  Found {len(results)} result(s):\n")
        for i, item in enumerate(results, 1):
            number_info = f" ({item['number']})" if item["number"] else ""
            print(f"    [{i}] {item['title']}{number_info}")
        print()

        try:
            selection = input("  Select a number to download (or 'b' to go back): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Bye!")
            break

        if selection.lower() == "b":
            print()
            continue

        try:
            idx = int(selection) - 1
            if idx < 0 or idx >= len(results):
                raise ValueError
        except ValueError:
            print("  Invalid selection.\n")
            continue

        chosen = results[idx]
        number_info = f" ({chosen['number']})" if chosen["number"] else ""
        print(f"\n  Selected: {chosen['title']}{number_info}")
        print(f"  URL:      {chosen['gme']}")

        if not is_official_source(chosen["gme"]):
            print("  ⚠ Skipped — URL is not from an official Ravensburger domain.\n")
            continue

        try:
            confirm = input("  Download? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n  Bye!")
            break

        if confirm != "y":
            print("  Download cancelled.\n")
            continue

        try:
            dest = download_gme(chosen["gme"], Path.cwd())
            print(f"\n  ✔ Saved to {dest}\n")
        except Exception as exc:
            print(f"\n  ✘ Download failed: {exc}\n")


if __name__ == "__main__":
    main()
