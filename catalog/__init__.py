"""
Algorithm catalog (discoverability layer).

This package provides a lightweight registry for "where is X?" questions:
- Is it a Bias / Adapter / Plugin / Representation operator / Suite?
- What are the recommended companion components?

It is intentionally *shallow*: it does not enforce how users decompose algorithms,
it only makes components discoverable.
"""

from .registry import CatalogEntry, get_catalog

__all__ = [
    "CatalogEntry",
    "get_catalog",
    "search_catalog",
    "list_catalog",
    "get_entry",
    "reload_catalog",
]


def search_catalog(query: str, *, kinds=None, tags=None, limit: int = 20):
    """Convenience wrapper for `get_catalog().search(...)`."""
    return get_catalog().search(query, kinds=kinds, tags=tags, limit=limit)


def list_catalog(*, kind: str | None = None, tag: str | None = None):
    """Convenience wrapper for `get_catalog().list(...)`."""
    return get_catalog().list(kind=kind, tag=tag)


def get_entry(key: str):
    """Convenience wrapper for `get_catalog().get(key)`."""
    return get_catalog().get(key)


def reload_catalog():
    """Reload catalog (useful after editing `catalog/entries.toml` or env var paths)."""
    return get_catalog(refresh=True)
