from __future__ import annotations

from typing import List

from ..registry import CatalogEntry
from ..store.mysql import MySQLCatalogStore, mysql_config_enabled


class MySQLCatalogProvider:
    name = "mysql_catalog"

    def load(self) -> List[CatalogEntry]:
        if not mysql_config_enabled():
            return []
        try:
            store = MySQLCatalogStore(readonly=True)
            return list(store.list_catalog_entries(profile="default", limit=None))
        except Exception:
            return []
