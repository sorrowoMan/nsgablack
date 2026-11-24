from __future__ import annotations
from blackbase.plugin import report_soft_error as _report_optional_failure

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
        except Exception as _fallback_error:
            _report_optional_failure(component=__name__, event='PostgresCatalogProvider.load.fallback_114', exc=_fallback_error)
            return []
