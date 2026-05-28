from __future__ import annotations

from typing import List

from ..registry import CatalogEntry
from ..store.postgres import PostgresCatalogStore, postgres_config_enabled


class PostgresCatalogProvider:
    name = "postgres_catalog"

    def load(self) -> List[CatalogEntry]:
        if not postgres_config_enabled():
            return []
        try:
            store = PostgresCatalogStore(readonly=True)
            return list(store.list_catalog_entries(profile="default", limit=None))
        except Exception:
            return []
