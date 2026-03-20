from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .contracts import HealthContract
from .sync import build_catalog_bundle
from .store.mysql import MySQLCatalogStore


@dataclass(frozen=True)
class CatalogAuditReport:
    total: int
    import_failures: int
    context_failures: int
    method_failures: int
    param_failures: int
    issues: List[str]


def audit_catalog(*, profile: str, runtime: bool = False) -> CatalogAuditReport:
    bundle = build_catalog_bundle(profile=profile, runtime=runtime)
    return _build_report(bundle.health)


def audit_catalog_to_mysql(*, profile: str, runtime: bool = False) -> CatalogAuditReport:
    bundle = build_catalog_bundle(profile=profile, runtime=runtime)
    store = MySQLCatalogStore()
    store.update_health(bundle.components, bundle.health)
    return _build_report(bundle.health)


def _build_report(health: List[HealthContract]) -> CatalogAuditReport:
    issues: List[str] = []
    for h in health:
        issues.extend(h.issues)
    return CatalogAuditReport(
        total=len(health),
        import_failures=sum(1 for h in health if not h.import_ok),
        context_failures=sum(1 for h in health if not h.context_ok),
        method_failures=sum(1 for h in health if not h.methods_ok),
        param_failures=sum(1 for h in health if not h.params_ok),
        issues=issues,
    )
