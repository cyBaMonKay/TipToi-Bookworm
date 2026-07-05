"""Shared type contracts for bookworm modules."""

from typing import TypedDict


class Product(TypedDict):
    """Catalog product item returned by scraping and used by the CLI."""

    title: str
    number: str
    gme: str
