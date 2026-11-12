"""Explicit federation of public, semantic-neutral Catalog providers.

``NSGABLACK_CATALOG_PROVIDERS`` is deployment configuration, not query input.
For example ``mlblack=mlblack.catalog.registry:get_catalog`` imports MLBlack's
public registry once and publishes it in a stable ``mlblack.`` key namespace.
Multiple providers are separated by commas or newlines. A configured provider
is required: import and contract failures must not publish a partial catalog.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import importlib
import inspect
import os
import re
from collections.abc import Iterable

from blackbase.catalog import Catalog, CatalogEntry


PROVIDERS_ENV = "NSGABLACK_CATALOG_PROVIDERS"


@dataclass(frozen=True)
class CatalogSource:
    namespace: str
    factory_path: str


def configured_catalog_sources(value: str | None = None) -> tuple[CatalogSource, ...]:
    """Validate the configured identities before importing any provider."""

    raw = os.environ.get(PROVIDERS_ENV, "") if value is None else value
    sources: list[CatalogSource] = []
    seen: set[str] = set()
    for item in re.split(r"[,\n]", str(raw)):
        item = item.strip()
        if not item:
            continue
        namespace, sep, factory_path = item.partition("=")
        namespace, factory_path = namespace.strip(), factory_path.strip()
        module, colon, attribute = factory_path.partition(":")
        if (
            not sep
            or not re.fullmatch(r"[a-z][a-z0-9_-]*", namespace)
            or namespace == "nsgablack"
            or not colon
            or not module
            or not attribute
        ):
            raise ValueError(
                f"Invalid {PROVIDERS_ENV} source {item!r}; expected "
                "namespace=module:factory with a non-nsgablack namespace"
            )
        if namespace in seen:
            raise ValueError(f"Duplicate Catalog provider namespace: {namespace}")
        seen.add(namespace)
        sources.append(CatalogSource(namespace, factory_path))
    return tuple(sources)


def _provider_entries(source: CatalogSource, *, refresh: bool) -> tuple[CatalogEntry, ...]:
    module_path, _, attribute_path = source.factory_path.partition(":")
    try:
        factory = importlib.import_module(module_path)
        for attribute in attribute_path.split("."):
            factory = getattr(factory, attribute)
        if not callable(factory):
            raise TypeError("Catalog provider must be callable")
        signature = inspect.signature(factory)
        accepts_refresh = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            or (parameter.name == "refresh" and parameter.kind != inspect.Parameter.POSITIONAL_ONLY)
            for parameter in signature.parameters.values()
        )
        result = factory(refresh=refresh) if accepts_refresh else factory()
        if isinstance(result, Catalog):
            values = tuple(result.list())
        elif isinstance(result, Iterable) and not isinstance(result, (str, bytes, dict)):
            values = tuple(result)
        else:
            raise TypeError("Catalog provider must return a shared Catalog or iterable of CatalogEntry")
        # Shared Catalog validates both record types and unique original keys.
        Catalog(values)
        return values
    except Exception as exc:
        raise RuntimeError(
            f"Required Catalog provider {source.namespace!r} ({source.factory_path}) failed: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def load_federated_entries(*, refresh: bool = False) -> tuple[CatalogEntry, ...]:
    """Materialize each public source without inferring its framework semantics.

    Only catalog identity and local catalog links are rewritten. Import paths,
    raw contracts, ML metadata, artifact/phase declarations and usage supplied
    by the owning registry retain their original meaning.
    """

    out: list[CatalogEntry] = []
    for source in configured_catalog_sources():
        entries = _provider_entries(source, refresh=refresh)
        keys = {entry.key: f"{source.namespace}.{entry.key}" for entry in entries}
        for entry in entries:
            out.append(
                replace(
                    entry,
                    key=keys[entry.key],
                    companions=tuple(keys.get(key, key) for key in entry.companions),
                    required_companions=tuple(keys.get(key, key) for key in entry.required_companions),
                    example_entry=keys.get(entry.example_entry, entry.example_entry),
                    metadata={
                        **dict(entry.metadata),
                        "catalog_framework": source.namespace,
                        "catalog_original_key": entry.key,
                    },
                )
            )
    return tuple(out)
