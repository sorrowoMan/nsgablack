from nsgablack.catalog import get_catalog
from tools.catalog_integrity_checker import CatalogIntegrityChecker


def test_plugin_context_contracts_are_enriched_in_catalog():
    entry = get_catalog(refresh=True).get("plugin.dynamic_switch")
    assert entry is not None
    assert tuple(entry.context_provides or ())
    assert "dynamic" in set(entry.context_provides)
    assert tuple(entry.context_notes or ())


def test_catalog_integrity_checker_strict_plugin_context_passes():
    checker = CatalogIntegrityChecker(
        check_context=True,
        check_usage=False,
        context_kinds=("plugin",),
        require_context_notes=True,
    )
    result = checker.run()
    assert not result.import_failures
    assert not result.context_warnings
