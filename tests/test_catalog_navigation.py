"""Catalog browse groups aggregate actual kinds without altering their records."""
from __future__ import annotations

import pytest

from nsgablack.catalog import dashboard, navigation
from nsgablack.catalog.facade import catalog_summary, list_entries, search_entries


def test_groups_partition_declared_kinds_and_keep_future_kinds_visible():
    kinds = [kind for group in navigation.GROUPS for kind in group.kinds]
    assert len(kinds) == len(set(kinds))
    assert len(navigation.PRIMARY_OPTIONS) == 9
    assert navigation.group_for_kind("new_domain_kind") == "group:tools"
    assert navigation.member_kinds("group:tools", ("tool", "new_domain_kind", "codec")) == (
        "new_domain_kind", "tool")
    counts = navigation.group_counts({"adapter": 3, "codec": 4, "new_domain_kind": 2})
    assert counts["all"] == sum(value for key, value in counts.items() if key != "all") == 9
    assert counts["group:tools"] == 2


def test_query_scope_preserves_other_filters_and_intersects_explicit_kinds():
    assert navigation.query_scope("all", {"tags": "test"}) == (None, {"tags": "test"})
    assert navigation.query_scope("codec") == ("codec", {})
    kind, filters = navigation.query_scope("group:model", {"tags": "x", "kind": "codec,adapter"})
    assert kind is None and filters == {"tags": "x", "kind": ("codec",)}
    assert navigation.query_scope("group:model", {"kind": "adapter"})[1]["kind"] == (
        "__catalog_navigation_empty__",)
    assert navigation.query_scope("group:tools", available_kinds=("new_domain_kind",))[1] == {
        "kind": ("new_domain_kind",)}
    assert dashboard._pick_default_kind("group:model", ("all", "codec")) == "group:model"
    assert navigation.contains_kind("group:model", "codec")
    assert not navigation.contains_kind("group:model", "adapter")


@pytest.fixture
def federated(monkeypatch):
    monkeypatch.setenv("NSGABLACK_CATALOG_PROVIDERS", "mlblack=mlblack.catalog.registry:get_catalog")
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "off")
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED_SOURCE", "registry")
    monkeypatch.setenv("NSGABLACK_CATALOG_KNOWLEDGE_ENABLED", "0")
    for loader in (dashboard._cached_summary, dashboard._cached_schema, dashboard._cached_source_info,
                   dashboard._cached_items, dashboard._cached_facets, dashboard._cached_other_kind_hits):
        loader.cache_clear()


@pytest.mark.parametrize("profile", ("default", "framework-core"))
def test_every_published_record_is_in_exactly_one_group_and_facets_match(federated, profile):
    entries = list_entries(profile=profile, source_mode="off", limit=None)
    summary = catalog_summary(profile=profile, source_mode="off")
    all_keys = {entry.key for entry in entries}
    seen = set()
    for group in navigation.PRIMARY_OPTIONS[1:]:
        payload = dashboard._load_items(profile, "framework", "", False, group, "", "all", (), "", "off")
        expected = {entry.key for entry in entries if navigation.contains_kind(group, entry.kind)}
        actual = {entry["key"] for entry in payload}
        assert actual == expected
        assert not seen.intersection(actual)
        seen.update(actual)
        facets = dashboard._load_facets(profile, "framework", "", False, group, "", "all", "", "off")
        assert facets["total"] == len(actual) == navigation.group_counts(summary["by_kind"])[group]
    assert seen == all_keys
    assert len(dashboard._load_items(profile, "framework", "", False, "all", "", "all", (), "", "off")) == len(entries)
    expected = search_entries("linear", profile=profile, source_mode="off", limit=1000,
                              field_filters={"kind": ("model", "codec", "head")})
    actual = dashboard._load_items(profile, "framework", "", False, "group:model", "linear", "all", (), "", "off")
    assert {item["key"] for item in actual} == {item.key for item in expected}
    hits = dashboard._other_kind_hits(query="bias.tabu", profile=profile, scope="framework",
        project_path=None, include_global=False, field="all", current_kind="group:search", source_mode="off")
    assert hits and set(hits) == {"group:problem"}


def _widget(elements, label):
    return next(item for item in elements if item.label == label)


@pytest.mark.parametrize("profile", ("default", "framework-core"))
def test_group_browsing_and_secondary_types_are_natural_and_old_links_work(federated, profile):
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    app = AppTest.from_string(
        "from nsgablack.catalog.dashboard import run_dashboard\n"
        f"run_dashboard(['--profile', {profile!r}, '--source-mode', 'off'])\n", default_timeout=90)
    app.query_params.update({"kind": "codec", "query": "linear"})
    app.run()
    assert not app.exception
    assert app.session_state["catalog_ui_kind"] == "codec", "Old concrete-kind links must remain concrete"
    primary = _widget(app.radio, "分类")
    assert len(primary.options) == 9
    assert app.session_state["catalog_ui::browse_kind"] == "group:model"
    assert app.session_state["catalog_ui::browse_subkind"] == "codec"
    subtype = _widget(app.selectbox, "组件类型")
    counts = catalog_summary(profile=profile, source_mode="off")["by_kind"]
    expected_options = {f"本组全部 · {navigation.group_counts(counts)['group:model']}"} | {
        f"{dashboard._kind_label(kind)} · {counts[kind]}"
        for kind in navigation.member_kinds("group:model", tuple(counts))}
    assert set(subtype.options) == expected_options

    primary.set_value("group:runtime").run()
    assert not app.exception
    assert app.session_state["catalog_ui_kind"] == "group:runtime"
    assert app.session_state["catalog_ui_query"] == "" and "query" not in app.query_params
    assert app.session_state["catalog_ui_result_keys"]
    subtype = _widget(app.selectbox, "组件类型")
    assert all("模型参数" not in option for option in subtype.options)
    subtype.set_value("plugin").run()
    assert not app.exception
    assert app.session_state["catalog_ui_kind"] == "plugin"
    visible_keys = set(app.session_state["catalog_ui_result_keys"])
    expected_keys = {entry.key for entry in list_entries(profile=profile, kind="plugin", source_mode="off", limit=None)}
    assert visible_keys and visible_keys <= expected_keys
    _widget(app.radio, "分类").set_value("all").run()
    assert not app.exception
    assert app.session_state["catalog_ui_kind"] == "all"
    assert not any(item.label == "组件类型" for item in app.selectbox)
