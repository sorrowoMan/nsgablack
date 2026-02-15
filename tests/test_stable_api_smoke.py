from __future__ import annotations


def test_stable_top_level_imports():
    import nsgablack

    assert isinstance(nsgablack.__version__, str)
    assert callable(nsgablack.get_catalog)


def test_stable_catalog_entry_points_importable():
    # The project treats catalog + suite/plugin/adapters as the stable entry path.
    from nsgablack.catalog import get_catalog

    c = get_catalog()
    assert c.get("suite.benchmark_harness") is not None
    assert c.get("plugin.benchmark_harness") is not None
    assert c.get("plugin.module_report") is not None


def test_profiler_plugin_importable():
    from nsgablack.plugins import ProfilerPlugin

    assert ProfilerPlugin is not None


