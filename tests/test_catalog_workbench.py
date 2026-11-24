"""Interaction coverage for the Catalog workbench without a browser process."""
from __future__ import annotations

import pytest
from types import SimpleNamespace
from nsgablack.catalog import dashboard

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


@pytest.fixture
def hosted_app(monkeypatch):
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "off")
    return AppTest.from_string(
        "from nsgablack.catalog.dashboard import run_dashboard\n"
        "run_dashboard(['--profile', 'default', '--kind', 'all', '--source-mode', 'off'])\n",
        default_timeout=30,
    )


def _widget(elements, label):
    return next(element for element in elements if element.label == label)


def _assert_no_exception(app):
    assert not app.exception, [item.message for item in app.exception]


def _query_value(app, key):
    value = app.query_params.get(key, "")
    return value[-1] if isinstance(value, list) else value


def _result_keys(app):
    keys = tuple(app.session_state["catalog_ui_result_keys"])
    assert len(keys) == len(set(keys))
    if keys:
        lists = [item for item in app.radio if str(item.key).startswith("catalog_ui::component_list::")]
        assert len(lists) == 1 and len(lists[0].options) == len(keys)
    return keys


def test_table_selection_and_next_keep_the_current_result_category():
    view = SimpleNamespace(session_state={"catalog_ui_kind": "all", "table": {"selection": {"rows": [1]}}})
    dashboard._callback_results_selection(view, table_key="table", item_keys=("adapter.a", "bias.b"))
    assert view.session_state["catalog_ui_selected"] == "bias.b"
    dashboard._callback_select_entry(view, target_key="tool.c", target_kind="tool")
    assert view.session_state["catalog_ui_selected"] == "tool.c"
    assert view.session_state["catalog_ui_kind"] == "all"
    view.session_state["table"] = {"selection": {"rows": []}}
    dashboard._callback_results_selection(view, table_key="table", item_keys=("adapter.a", "bias.b"))
    assert view.session_state["catalog_ui_selected"] == dashboard._NO_SELECTION


def test_show_more_updates_both_window_state_and_restorable_url():
    view = SimpleNamespace(session_state={"window": 250}, query_params={"page_size": "250"})
    dashboard._callback_show_more(view, page_size_key="window", total=279)
    assert view.session_state["window"] == 279
    assert view.query_params["page_size"] == "279"


def test_hosted_workbench_removes_unavailable_sources_before_first_render(hosted_app):
    app = hosted_app
    app.query_params.update({"scope": "project", "project_path": "C:/private/project",
                             "db_path": "postgresql://unused.invalid/catalog", "source_mode": "only"})
    app.run()
    _assert_no_exception(app)
    assert {widget.label for widget in app.text_input} == {"搜索组件"}
    assert all(widget.label not in {"Project Path", "DB Path / URL", "Source Mode", "视图"}
               for group in (app.text_input, app.selectbox, app.radio) for widget in group)
    assert app.session_state["catalog_ui_scope"] == "framework"
    assert app.session_state["catalog_ui_source_mode"] == "off"
    assert _query_value(app, "scope") == "framework"
    assert _query_value(app, "source_mode") == "off"
    assert "project_path" not in app.query_params and "db_path" not in app.query_params
    assert _result_keys(app)
    assert not app.dataframe, "Standard browsing must use the selectable component list"


def test_workbench_category_browses_all_entries_and_profile_preserves_search(hosted_app):
    app = hosted_app.run()
    _widget(app.text_input, "搜索组件").input("贝叶斯引导").run()
    _assert_no_exception(app)
    assert app.session_state["catalog_ui_query"] == "贝叶斯引导"
    assert _query_value(app, "query") == "贝叶斯引导"
    assert "adapter.bayesian_optimization" in _result_keys(app)

    _widget(app.radio, "分类").set_value("group:search").run()
    _widget(app.selectbox, "组件类型").set_value("adapter").run()
    _assert_no_exception(app)
    assert app.session_state["catalog_ui_kind"] == "adapter"
    assert _query_value(app, "kind") == "adapter"
    assert app.session_state["catalog_ui_query"] == ""
    assert "query" not in app.query_params

    _widget(app.text_input, "搜索组件").input("贝叶斯引导").run()
    _assert_no_exception(app)

    _widget(app.selectbox, "目录范围").set_value("framework-core").run()
    _assert_no_exception(app)
    assert app.session_state["catalog_ui_profile"] == "framework-core"
    assert _query_value(app, "profile") == "framework-core"
    assert app.session_state["catalog_ui_kind"] == "adapter"
    assert app.session_state["catalog_ui_query"] == "贝叶斯引导"
    assert "adapter.bayesian_optimization" in _result_keys(app)


@pytest.mark.parametrize(("label", "query", "selected"), [
    ("贝叶斯优化", "贝叶斯引导", "adapter.bayesian_optimization"),
    ("GA + VNS 编排", "GA停滞VNS精修", "adapter.search_plan"),
    ("解池操作", "解池", "tool.solution_pool"),
    ("扩展 Unit", "种群扩展字段", "tool.population_change"),
])
def test_search_intent_clears_existing_filters_and_selects_its_component(hosted_app, label, query, selected):
    app = hosted_app
    app.query_params.update({"kind": "adapter", "query": "ns", "f_tags": "core"})
    app.run()
    _assert_no_exception(app)
    assert app.session_state["catalog_ui::facet::framework::adapter::tags"]
    _widget(app.button, label).click().run()
    _assert_no_exception(app)
    assert app.session_state["catalog_ui_query"] == query
    assert app.session_state["catalog_ui_field"] == "all"
    assert app.session_state["catalog_ui_kind"] == "all"
    assert app.session_state["catalog_ui_selected"] == selected
    assert _query_value(app, "query") == query
    assert _query_value(app, "selected") == selected
    assert not any(key.startswith("f_") for key in app.query_params)
    assert not app.session_state.filtered_state.get("catalog_ui::facet::framework::adapter::tags")
    assert not app.session_state.filtered_state.get("catalog_ui::facet::framework::all::tags")
    assert selected in _result_keys(app)


def test_component_list_selection_preserves_category_query_and_url(hosted_app):
    app = hosted_app
    app.query_params.update({"kind": "all", "query": "ns"})
    app.run()
    _assert_no_exception(app)
    keys = _result_keys(app)
    assert len(keys) > 1
    chosen = keys[1]
    component_list = next(item for item in app.radio if str(item.key).startswith("catalog_ui::component_list::"))
    component_list.set_value(chosen).run()
    _assert_no_exception(app)
    assert app.session_state["catalog_ui_selected"] == chosen
    assert _query_value(app, "selected") == chosen
    assert app.session_state["catalog_ui_kind"] == "all"
    assert app.session_state["catalog_ui_query"] == "ns"
    assert _result_keys(app) == keys
    assert any("catalog-entry-key" in item.value and chosen in item.value for item in app.markdown)


def test_empty_search_keeps_detail_and_clear_selection_survives_rerun(hosted_app):
    app = hosted_app
    app.query_params.update({"kind": "all", "query": "ns", "selected": "adapter.nsga2"})
    app.run()
    _assert_no_exception(app)
    _widget(app.text_input, "搜索组件").input("__no_such_component_20261026__").run()
    _assert_no_exception(app)
    assert _result_keys(app) == ()
    assert app.session_state["catalog_ui_selected"] == "adapter.nsga2"
    assert any("catalog-entry-key" in item.value and "adapter.nsga2" in item.value for item in app.markdown)
    _widget(app.button, "清除选中").click().run()
    app.run()
    _assert_no_exception(app)
    assert app.session_state["catalog_ui_selected"] == dashboard._NO_SELECTION
    assert "selected" not in app.query_params


def test_full_browse_mode_keeps_identity_table_as_an_explicit_option(hosted_app):
    app = hosted_app
    app.query_params.update({"kind": "adapter", "query": "ns", "column_mode": "full"})
    app.run()
    _assert_no_exception(app)
    assert app.dataframe
    assert tuple(app.dataframe[0].value["Key"].astype(str)) == tuple(app.session_state["catalog_ui_result_keys"])
    assert not any(str(item.key).startswith("catalog_ui::component_list::") for item in app.radio)


def test_detail_tabs_can_return_to_usage_without_losing_selection(hosted_app):
    app = hosted_app
    app.query_params.update({"kind": "adapter", "selected": "adapter.fixed_candidate"})
    app.run()
    for tab in ("interface", "overview", "relations", "source", "overview"):
        _widget(app.radio, "详情 Tab").set_value(tab).run()
        _assert_no_exception(app)
        assert _query_value(app, "detail_tab") == tab
        assert app.session_state["catalog_ui_selected"] == "adapter.fixed_candidate"
        assert any(item.label == "原始组件声明" for item in app.expander) == (tab == "interface")


def test_display_settings_can_change_repeatedly_and_survive_reruns(hosted_app):
    app = hosted_app.run()
    settings = (
        ("selectbox", "结果排序", "sort_by", ("title", "key", "default")),
        ("radio", "方向", "sort_dir", ("desc", "asc")),
        ("selectbox", "浏览方式", "column_mode", ("full", "compact", "standard")),
        ("selectbox", "显示数量", "page_size", (25, 100, 50)),
        ("radio", "结果折叠", "results_collapse", ("collapsed", "expanded")),
    )
    for family, label, parameter, values in settings:
        for value in values:
            _widget(getattr(app, family), label).set_value(value).run()
            _assert_no_exception(app)
            assert _query_value(app, parameter) == str(value)
            app.run()
            assert _widget(getattr(app, family), label).value == value
