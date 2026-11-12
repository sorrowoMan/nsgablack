"""Restorable URL filters must not overwrite later workbench interactions."""
from __future__ import annotations

import pytest

from nsgablack.catalog import dashboard

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


@pytest.fixture(params=("default", "framework-core"))
def filtered_app(monkeypatch, request):
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED_SOURCE", "registry")
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "off")
    monkeypatch.setenv("NSGABLACK_CATALOG_KNOWLEDGE_ENABLED", "0")
    app = AppTest.from_string(
        "from nsgablack.catalog.dashboard import run_dashboard\n"
        f"run_dashboard(['--profile', {request.param!r}, '--kind', 'adapter', '--source-mode', 'off'])\n",
        default_timeout=60,
    )
    app.query_params.update({"kind": "adapter", "query": "ns", "f_tags": "core"})
    return app


def _assert_healthy(app):
    assert not app.exception, [item.message for item in app.exception]


def _facet(app, kind="adapter"):
    return app.session_state.filtered_state.get(f"catalog_ui::facet::framework::{kind}::tags", ())


def test_user_can_remove_a_tag_restored_from_a_deep_link(filtered_app):
    app = filtered_app.run()
    _assert_healthy(app)
    assert list(_facet(app)) == ["core"]
    widget = next(item for item in app.multiselect if item.key == "catalog_ui::facet::framework::adapter::tags")
    widget.set_value([]).run()
    _assert_healthy(app)
    assert not _facet(app)
    assert "f_tags" not in app.query_params
    app.run()
    _assert_healthy(app)
    assert not _facet(app), "A later rerun must not restore the removed URL filter"


def test_clear_filters_removes_the_restored_url_filter(filtered_app):
    app = filtered_app.run()
    _assert_healthy(app)
    assert list(_facet(app)) == ["core"]
    next(item for item in app.button if item.label == "清空字段筛选").click().run()
    _assert_healthy(app)
    assert not _facet(app)
    assert "f_tags" not in app.query_params
    assert app.session_state["catalog_ui_query"] == "ns", "Clearing facets must preserve the search query"
    app.run()
    _assert_healthy(app)
    assert not _facet(app)


def test_classification_change_does_not_copy_old_url_facets(filtered_app):
    app = filtered_app.run()
    _assert_healthy(app)
    assert list(_facet(app)) == ["core"]
    next(item for item in app.radio if item.label == "分类").set_value("all").run()
    _assert_healthy(app)
    assert app.session_state["catalog_ui_kind"] == "all"
    assert not _facet(app, "all"), "The target category has no filter history to restore"
    assert "f_tags" not in app.query_params
    assert app.session_state["catalog_ui_query"] == ""
    assert app.session_state["catalog_ui_field"] == "all"
    assert "query" not in app.query_params


def test_sidebar_classification_browses_full_category_after_an_empty_search(filtered_app):
    app = filtered_app
    app.query_params.pop("f_tags", None)
    app.query_params["query"] = "bias.tabu"
    app.run()
    _assert_healthy(app)
    assert any("当前分类没有命中，但其他分类里有结果" in item.value for item in app.info)

    for kind in ("plugin", "adapter"):
        next(item for item in app.radio if item.label == "分类").set_value(dashboard._navigation.group_for_kind(kind)).run()
        next(item for item in app.selectbox if item.label == "组件类型").set_value(kind).run()
        _assert_healthy(app)
        assert app.session_state["catalog_ui_kind"] == kind
        assert app.session_state["catalog_ui_query"] == ""
        assert app.session_state["catalog_ui_field"] == "all"
        assert "query" not in app.query_params
        assert not any(str(key).startswith("f_") for key in app.query_params)
        visible_keys = set(app.session_state["catalog_ui_result_keys"])
        expected = dashboard._load_items(app.session_state["catalog_ui_profile"], "framework", "", False,
                                         kind, "", "all", (), "", "off")
        assert visible_keys and visible_keys <= {entry["key"] for entry in expected}
        assert not any("当前分类没有命中，但其他分类里有结果" in item.value for item in app.info)

        if kind == "plugin":
            # Reproduce the same trap from another category before moving back.
            next(item for item in app.text_input if item.label == "搜索组件").input("bias.tabu").run()
            _assert_healthy(app)
            assert any("当前分类没有命中，但其他分类里有结果" in item.value for item in app.info)


def test_other_category_suggestions_honor_active_url_filters(filtered_app):
    app = filtered_app
    app.query_params.update({"query": "bias.tabu", "f_tags": "core"})
    app.run()
    _assert_healthy(app)
    assert list(_facet(app)) == ["core"]
    assert not any("当前分类没有命中，但其他分类里有结果" in item.value for item in app.info), (
        "Tabu is outside the current kind but does not match the active core tag; "
        "unfiltered global results must not be advertised as matching the same query"
    )


def test_reset_search_clears_query_field_and_url_facets_but_keeps_category(filtered_app):
    app = filtered_app
    app.query_params["field"] = "name"
    app.run()
    _assert_healthy(app)
    assert list(_facet(app)) == ["core"]
    next(item for item in app.button if item.label == "重置搜索").click().run()
    _assert_healthy(app)
    assert app.session_state["catalog_ui_query"] == ""
    assert app.session_state["catalog_ui_field"] == "all"
    assert app.session_state["catalog_ui_kind"] == "adapter"
    assert not _facet(app)
    assert "query" not in app.query_params
    assert not any(str(key).startswith("f_") for key in app.query_params)
    assert app.session_state["catalog_ui_result_keys"]
    app.run()
    _assert_healthy(app)
    assert app.session_state["catalog_ui_query"] == ""
    assert app.session_state["catalog_ui_field"] == "all"
    assert not _facet(app)


def test_cross_category_cache_identity_includes_active_filters(monkeypatch):
    calls = []

    def search(query, **kwargs):
        calls.append(kwargs)
        assert query == "bias.tabu"
        if kwargs["field_filters"]:
            return []
        from types import SimpleNamespace
        return [SimpleNamespace(kind="bias")]

    monkeypatch.setattr(dashboard, "search_entries", search)
    dashboard._cached_other_kind_hits.cache_clear()
    common = dict(query="bias.tabu", profile="framework-core", scope="framework", project_path=None,
                  include_global=False, field="all", current_kind="adapter", source_mode="off")
    assert list(dashboard._cached_other_kind_hits(**common)) == ["bias"]
    filters = (("tags", ("core",)),)
    assert dashboard._cached_other_kind_hits(**common, filters_key=filters) == {}
    assert dashboard._cached_other_kind_hits(**common, filters_key=filters) == {}
    assert [item["field_filters"] for item in calls] == [{}, {"tags": "core"}]
    assert dashboard._cached_other_kind_hits.cache_info().misses == 2
    assert dashboard._cached_other_kind_hits.cache_info().hits == 1
