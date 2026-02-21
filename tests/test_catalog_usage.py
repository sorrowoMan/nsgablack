from nsgablack.catalog.registry import Catalog, CatalogEntry
from nsgablack.catalog.usage import build_usage_profile


def test_build_usage_profile_infers_plugin_wiring():
    entry = CatalogEntry(
        key="plugin.demo",
        title="DemoPlugin",
        kind="plugin",
        import_path="nsgablack.plugins.ops.module_report:ModuleReportPlugin",
    )
    usage = build_usage_profile(entry)
    joined = "\n".join(usage.minimal_wiring)
    assert "solver.add_plugin" in joined
    assert "ModuleReportPlugin" in joined


def test_build_usage_profile_infers_adapter_control_plane_wiring():
    entry = CatalogEntry(
        key="adapter.demo",
        title="DemoAdapter",
        kind="adapter",
        import_path="nsgablack.core.adapters:NSGA2Adapter",
    )
    usage = build_usage_profile(entry)
    joined = "\n".join(usage.minimal_wiring)
    assert "solver.set_adapter(" in joined
    assert "NSGA2Adapter" in joined


def test_catalog_search_usage_field_matches_use_when():
    entry = CatalogEntry(
        key="plugin.demo",
        title="DemoPlugin",
        kind="plugin",
        import_path="nsgablack.plugins.ops.module_report:ModuleReportPlugin",
        use_when=("需要生成模块审计报告时",),
    )
    c = Catalog([entry])
    hits = c.search("审计", fields="usage")
    assert len(hits) == 1
    assert hits[0].key == "plugin.demo"


def test_global_catalog_entries_have_usage_contracts():
    from nsgablack.catalog import get_catalog

    entries = get_catalog(refresh=True).list()
    assert entries
    for e in entries:
        assert tuple(getattr(e, "use_when", ()) or ())
        assert tuple(getattr(e, "minimal_wiring", ()) or ())
        assert tuple(getattr(e, "required_companions", ()) or ())
        assert tuple(getattr(e, "config_keys", ()) or ())
        assert str(getattr(e, "example_entry", "") or "").strip()
