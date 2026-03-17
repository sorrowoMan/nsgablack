"""
Algorithm catalog (discoverability layer).

This package provides a lightweight registry for "where is X?" questions:
- Is it a Bias / Adapter / Plugin / Representation operator / Suite?
- What are the recommended companion components?

It is intentionally *shallow*: it does not enforce how users decompose algorithms,
it only makes components discoverable.
"""

from .registry import CatalogEntry, get_catalog
from .usage import CatalogUsage, build_usage_profile, enrich_context_contracts, enrich_usage_contracts

__all__ = [
    "CatalogEntry",
    "get_catalog",
    "search_catalog",
    "list_catalog",
    "get_entry",
    "reload_catalog",
    "CatalogUsage",
    "build_usage_profile",
    "enrich_context_contracts",
    "enrich_usage_contracts",
]


def search_catalog(query: str, *, kinds=None, tags=None, limit: int = 20, profile: str | None = None):
    """Convenience wrapper for `get_catalog().search(...)`."""
    return get_catalog(profile=profile).search(query, kinds=kinds, tags=tags, limit=limit)


def list_catalog(*, kind: str | None = None, tag: str | None = None, profile: str | None = None):
    """Convenience wrapper for `get_catalog().list(...)`."""
    return get_catalog(profile=profile).list(kind=kind, tag=tag)


def get_entry(key: str):
    """Convenience wrapper for `get_catalog().get(key)`."""
    return get_catalog().get(key)


def reload_catalog(*, profile: str | None = None):
    """Reload catalog (useful after editing `catalog/entries.toml` or env var paths)."""
    return get_catalog(refresh=True, profile=profile)
