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
            payloads = store.load_entries()
        except Exception:
            return []
        out: List[CatalogEntry] = []
        for item in payloads:
            try:
                out.append(
                    CatalogEntry(
                        key=str(item.get("key", "")).strip(),
                        title=str(item.get("title", "")).strip(),
                        kind=str(item.get("kind", "")).strip().lower(),
                        import_path=str(item.get("import_path", "")).strip(),
                        tags=tuple(item.get("tags") or ()),
                        summary=str(item.get("summary", "") or "").strip(),
                        companions=tuple(item.get("companions") or ()),
                        context_requires=tuple(item.get("context_requires") or ()),
                        context_provides=tuple(item.get("context_provides") or ()),
                        context_mutates=tuple(item.get("context_mutates") or ()),
                        context_cache=tuple(item.get("context_cache") or ()),
                        context_notes=tuple(item.get("context_notes") or ()),
                        use_when=tuple(item.get("use_when") or ()),
                        minimal_wiring=tuple(item.get("minimal_wiring") or ()),
                        required_companions=tuple(item.get("required_companions") or ()),
                        config_keys=tuple(item.get("config_keys") or ()),
                        example_entry=str(item.get("example_entry", "") or "").strip(),
                    )
                )
            except Exception:
                continue
        return [e for e in out if e.key and e.kind and e.import_path]
