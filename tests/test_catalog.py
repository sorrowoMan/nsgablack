from nsgablack.catalog import get_catalog


def test_catalog_search_basic():
    catalog = get_catalog()

    hits = catalog.search("vns")
    assert any(e.key == "adapter.vns" for e in hits)

    hits = catalog.search("monte")
    assert any(e.key == "plugin.monte_carlo_eval" for e in hits)


def test_catalog_entry_load_smoke():
    catalog = get_catalog()

    entry = catalog.get("plugin.checkpoint_resume")
    assert entry is not None
    loaded = entry.load()
    assert callable(loaded)


def test_catalog_companions_integrity():
    catalog = get_catalog()

    for entry in catalog.list():
        for key in entry.companions:
            assert catalog.get(key) is not None, (entry.key, key)
