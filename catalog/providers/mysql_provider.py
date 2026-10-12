from __future__ import annotations
from blackbase.plugin import report_soft_error as _report_optional_failure

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
        except Exception as _fallback_error:
            _report_optional_failure(component=__name__, event='MySQLCatalogProvider.load.fallback_113', exc=_fallback_error)
            return []
