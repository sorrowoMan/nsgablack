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
from .sync import build_catalog_bundle
from .api_index import (
    build_api_index_bundle,
    export_api_index_docs,
    export_default_api_index_docs,
    get_api_index_entry_from_mysql,
    load_api_index_from_mysql,
    search_api_index_from_mysql,
    sync_api_index_to_mysql,
)
from .api_doc import (
    export_api_doc_template,
    get_api_doc_entry_from_mysql,
    import_api_doc_jsonl,
    list_api_doc_gaps_from_mysql,
    seed_api_doc_params_from_ast,
)
from .audit import audit_catalog, audit_catalog_to_mysql
from .export import export_catalog_docs, export_default_docs

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
    "build_catalog_bundle",
    "build_api_index_bundle",
    "audit_catalog",
    "audit_catalog_to_mysql",
    "export_catalog_docs",
    "export_default_docs",
    "sync_api_index_to_mysql",
    "load_api_index_from_mysql",
    "search_api_index_from_mysql",
    "get_api_index_entry_from_mysql",
    "export_api_index_docs",
    "export_default_api_index_docs",
    "export_api_doc_template",
    "import_api_doc_jsonl",
    "get_api_doc_entry_from_mysql",
    "list_api_doc_gaps_from_mysql",
    "seed_api_doc_params_from_ast",
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
