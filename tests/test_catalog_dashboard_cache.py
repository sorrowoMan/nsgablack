"""Cache contracts and the real dashboard branch that uses keyword-only loads."""
from __future__ import annotations

import inspect
import json

import pytest

from nsgablack.catalog import dashboard, dashboard_shell


@pytest.fixture
def isolated_loader_registry(monkeypatch):
    monkeypatch.setattr(dashboard_shell, "_MEMOIZED_LOADER_REGISTRY", {})


def test_keyword_only_loader_caches_equivalent_calls(isolated_loader_registry):
    calls = []

    def load(query, *, profile="framework-core", limit=24):
        calls.append((query, profile, limit))
        return {"query": query, "profile": profile, "limit": limit}

    cached = dashboard_shell.memoize_loader(load)
    expected = cached("bias")
    assert cached(query="bias", limit=24, profile="framework-core") == expected
    assert cached(profile="framework-core", query="bias", limit=24) == expected
    assert calls == [("bias", "framework-core", 24)]
    assert cached.cache_info().hits == 2


@pytest.mark.parametrize("clone_result", [True, False])
def test_loader_cache_preserves_clone_policy(isolated_loader_registry, clone_result):
    original = {"items": ["adapter.vns"]}

    def load(*, query):
        return original

    cached = dashboard_shell.memoize_loader(load, clone_result=clone_result)
    first = cached(query="vns")
    first["items"].append("changed")
    original["items"].append("source-changed")
    second = cached(query="vns")
    if clone_result:
        assert second == {"items": ["adapter.vns"]}
        assert second is not first and first is not original
    else:
        assert second is first is original
    cached.cache_clear()
    assert cached.cache_info().currsize == 0


def test_keyword_cache_records_miss_then_hit(isolated_loader_registry, monkeypatch, tmp_path):
    trace_path = tmp_path / "queries.jsonl"
    monkeypatch.setenv(dashboard_shell.QUERY_TRACE_PATH_ENV, str(trace_path))

    def load(*, query, limit=24):
        return query, limit

    cached = dashboard_shell.memoize_loader(load)
    cached(query="bias")
    cached(limit=24, query="bias")
    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert [event["cache_status"] for event in events] == ["miss", "hit"]
    assert all(event["loader"] == "load" for event in events)
    assert events[-1]["cache_hits"] == 1
    assert events[-1]["cache_misses"] == events[-1]["cache_size"] == 1


def test_loader_reload_reuses_cache_and_refreshes_callable(isolated_loader_registry):
    def make_loader(version):
        def load(*, query):
            return version, query
        return load

    first = dashboard_shell.memoize_loader(make_loader("before"))
    assert first(query="cached") == ("before", "cached")
    reloaded = dashboard_shell.memoize_loader(make_loader("after"))
    assert reloaded is first
    assert reloaded(query="cached") == ("before", "cached")
    assert reloaded(query="new") == ("after", "new")


def test_changed_loader_signature_invalidates_previous_cache(isolated_loader_registry):
    def load(*, query):
        return "before", query

    cached = dashboard_shell.memoize_loader(load)
    assert cached(query="bias") == ("before", "bias")

    def updated(*, query, limit=24):
        return "after", query, limit

    updated.__qualname__ = load.__qualname__
    reloaded = dashboard_shell.memoize_loader(updated)
    assert reloaded is cached
    assert reloaded.cache_info().currsize == 0
    assert reloaded(query="bias") == ("after", "bias", 24)


def test_loader_type_error_propagates_without_retry(isolated_loader_registry):
    calls = []

    def load(*, query):
        calls.append(query)
        raise TypeError("provider rejected query")

    cached = dashboard_shell.memoize_loader(load)
    with pytest.raises(TypeError, match="provider rejected query"):
        cached(query="bias")
    assert calls == ["bias"]
    assert cached.cache_info().currsize == 0


@pytest.mark.parametrize("name", [
    "source_info", "summary", "schema", "facets", "items", "selected", "neighbors", "other_kind_hits",
])
def test_every_dashboard_loader_accepts_keyword_calls(monkeypatch, name):
    # Exercise every real cached read against the registry, including nested cache calls.
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED_SOURCE", "registry")
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "off")
    loads = {
        "source_info": dashboard._load_source_info,
        "summary": dashboard._load_summary,
        "schema": dashboard._load_schema,
        "facets": dashboard._load_facets,
        "items": dashboard._load_items,
        "selected": dashboard._load_selected_entry,
        "neighbors": dashboard._load_neighbors,
        "other_kind_hits": dashboard._other_kind_hits,
    }
    loader = loads[name]
    signature = inspect.signature(loader)
    values = {
        "profile": "framework-core", "scope": "framework", "project_path": "", "include_global": False,
        "db_path": "", "source_mode": "off", "kind": "adapter", "current_kind": "adapter",
        "query": "bias", "search_field": "all", "field": "all", "filters_key": (),
        "selected_key": "adapter.vns", "limit": 24,
    }
    cached = getattr(dashboard, f"_cached_{name}")
    cached.cache_clear()
    arguments = {key: values[key] for key in signature.parameters}
    result = cached(**arguments)
    assert cached(**dict(reversed(tuple(arguments.items())))) == result
    assert cached.cache_info().misses == cached.cache_info().hits == 1


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_dashboard_empty_category_can_switch_to_other_kind(monkeypatch, profile):
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED_SOURCE", "registry")
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "off")
    dashboard._cached_other_kind_hits.cache_clear()
    app = AppTest.from_string(
        "from nsgablack.catalog.dashboard import run_dashboard\n"
        f"run_dashboard(['--profile', {profile!r}, '--kind', 'adapter', '--source-mode', 'off'])\n",
        default_timeout=30,
    ).run()
    assert not app.exception, [item.message for item in app.exception]
    search = next(widget for widget in app.text_input if widget.label == "搜索组件")
    search.input("bias.tabu").run()
    assert not app.exception, [item.message for item in app.exception]
    assert app.session_state["catalog_ui_kind"] == "adapter"
    assert any("当前分类没有命中，但其他分类里有结果" in item.value for item in app.info)
    assert dashboard._cached_other_kind_hits.cache_info().misses == 1
    switch = next(button for button in app.button
                  if button.key == "catalog_ui::switch_kind::framework::adapter::bias")
    switch.click().run()
    assert not app.exception, [item.message for item in app.exception]
    assert app.session_state["catalog_ui_kind"] == "bias"
    assert app.session_state["catalog_ui_query"] == "bias.tabu"
    assert "bias.tabu" in app.session_state["catalog_ui_result_keys"]
