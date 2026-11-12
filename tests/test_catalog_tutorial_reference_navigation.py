"""Real migration books lead to their own indexed assembly guides."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from nsgablack.adapters.unit_backed import UnitBackedAdapter
from nsgablack.catalog import dashboard, examples, examples_ui, registry
from nsgablack.catalog.curation_provider import DeepSeekGenerator
from nsgablack.units import UnitBinding

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

ORIGIN = "mlblack.nsgablack_symbolic.orthogonal_basis_outer"
TARGET = "mlblack.representation.symbolic_expression"
UNKNOWN = "mlblack.unregistered.tutorial_destination"
DEFAULT_ONLY = "doc.user_guide.catalog"


def _forbidden(*args, **kwargs):
    raise AssertionError("Reading a tutorial must not call a model or build an algorithm Unit")


@pytest.fixture
def tutorial_index(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    roots = {name: root.parent / name for name in ("nsgablack", "mlblack", "blackbase")}
    index = {"schema": examples.SCHEMA, "publication_digest": None, "entries": {}, "examples": {}, "issues": []}
    expected = {}
    for name in ("ml_symbolic_legacy_boundaries", "ml_symbolic_fixed_applications", "ml_symbolic_function_pool_applications"):
        manifest = tomllib.loads((root / "catalog/example_manifests" / f"{name}.toml").read_text(encoding="utf-8-sig"))
        expected[name] = set()
        for spec in manifest["example"]:
            record = examples._base_record(spec, roots, None)
            index["examples"][record["id"]] = record
            for key in record["component_keys"]:
                index["entries"].setdefault(key, []).append(record["id"])
                expected[name].add(key)
    examples.validate_example_index(index)
    path = tmp_path / "tutorial-index.json"
    path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv(examples_ui.INDEX_ENV, str(path))
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED_SOURCE", "registry")
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "off")
    monkeypatch.setenv("NSGABLACK_CATALOG_PROVIDERS", "mlblack=mlblack.catalog.registry:get_catalog")
    monkeypatch.setenv("NSGABLACK_CATALOG_KNOWLEDGE_ENABLED", "0")
    monkeypatch.setattr(DeepSeekGenerator, "_complete", _forbidden)
    monkeypatch.setattr(UnitBinding, "build", _forbidden)
    monkeypatch.setattr(UnitBackedAdapter, "ensure_unit", _forbidden)
    for name in ("_cached_summary", "_cached_schema", "_cached_source_info", "_cached_items", "_cached_facets",
                 "_cached_selected", "_cached_neighbors", "_cached_other_kind_hits"):
        getattr(dashboard, name).cache_clear()
    examples_ui._load_snapshot.cache_clear()
    for profile in ("default", "framework-core"):
        registry.get_source_catalog(profile=profile, refresh=True)
    return path, index, expected


def _page(profile):
    app = AppTest.from_string(
        "from nsgablack.catalog.dashboard import run_dashboard\n"
        f"run_dashboard(['--profile', {profile!r}, '--source-mode', 'off'])\n",
        default_timeout=90,
    )
    app.query_params.update({"kind": "all", "selected": ORIGIN, "detail_tab": "overview"})
    return app


def _reference_keys(container):
    return {str(item.key).rsplit("::", 1)[-1] for item in container.button
            if "::tutorial_reference::" in str(item.key)}


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_actual_migration_books_open_all_their_own_guides_and_return(tutorial_index, profile):
    _, _, expected = tutorial_index
    app = _page(profile).run()
    assert not app.exception
    assert app.session_state["catalog_ui_selected"] == ORIGIN
    assert any(item.value == "**教程中提到的用法**" for item in app.markdown)
    fixed = next(item for item in app.expander if item.label == "固定符号/基集合Case · 11 个组件")
    function_pool = next(item for item in app.expander if item.label == "函数池实际消费 · 9 个组件")
    assert _reference_keys(fixed) == expected["ml_symbolic_fixed_applications"]
    assert _reference_keys(function_pool) == expected["ml_symbolic_function_pool_applications"]
    assert not (_reference_keys(fixed) & _reference_keys(function_pool))
    assert "不表示组件等价" in "\n".join(item.value for item in app.caption)
    next(item for item in fixed.button if str(item.key).endswith("::" + TARGET)).click().run()
    assert not app.exception
    assert app.session_state["catalog_ui_selected"] == TARGET
    assert app.query_params["detail_tab"] in ("overview", ["overview"])
    assert any("参数" in item.value or "表达式" in item.value for item in app.markdown)
    next(item for item in app.button if str(item.key).startswith("catalog_ui::stack::")
         and str(item.key).endswith("::" + ORIGIN)).click().run()
    assert not app.exception
    assert app.session_state["catalog_ui_selected"] == ORIGIN
    assert _reference_keys(app) == (expected["ml_symbolic_fixed_applications"]
                                    | expected["ml_symbolic_function_pool_applications"])


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_unregistered_and_out_of_profile_targets_stay_hidden(tutorial_index, profile):
    """Extra index bindings cannot invent components or widen the read profile."""
    path, real_index, expected = tutorial_index
    index = deepcopy(real_index)
    record = index["examples"]["ml-symbolic-fixed-expression-application"]
    # Deliberately add two index-only bindings. The source chapter is unchanged;
    # neither the renderer nor its all-kind query may bypass the live Catalog.
    for key in (UNKNOWN, DEFAULT_ONLY):
        record["component_keys"].append(key)
        index["entries"][key] = [record["id"]]
    record["source_digest"] = examples._source_digest(record)
    examples.validate_example_index(index)
    path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    examples_ui._load_snapshot.cache_clear()
    app = _page(profile).run()
    assert not app.exception
    keys = _reference_keys(app)
    assert UNKNOWN not in keys
    expected_keys = expected["ml_symbolic_fixed_applications"] | expected["ml_symbolic_function_pool_applications"]
    assert keys == expected_keys | ({DEFAULT_ONLY} if profile == "default" else set())


def test_document_navigation_query_preserves_current_read_route(monkeypatch):
    calls = []
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.setattr(dashboard._examples, "render_examples", lambda *args, **kwargs: None)
    monkeypatch.setattr(dashboard._examples, "examples_snapshot", lambda: {
        "available": True, "index": {"entries": {}, "examples": {}, "issues": []}})
    monkeypatch.setattr(dashboard, "_cached_items", lambda *args: calls.append(args) or ())
    app = AppTest.from_string(
        "import streamlit as st\n"
        "from nsgablack.catalog.dashboard import _render_detail\n"
        "st.session_state.update({'catalog_ui_profile':'framework-core', 'catalog_ui_project_path':'C:/scoped/project',\n"
        "    'catalog_ui_include_global':True, 'catalog_ui_db_path':'scoped-reader', 'catalog_ui_source_mode':'only'})\n"
        "_render_detail(st, entry={'key':'example', 'kind':'tool', 'import_path':''}, neighbors={},\n"
        "    source_info={}, deep_link_query='', scope='project', kind='tool', detail_tab='overview',\n"
        "    expanded_relation_groups=())\n",
        default_timeout=30,
    ).run()
    assert not app.exception
    assert calls == [("framework-core", "project", "C:/scoped/project", True, "all", "", "all", (),
                      "scoped-reader", "only")]
