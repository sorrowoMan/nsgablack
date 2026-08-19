import runpy
from pathlib import Path
from urllib.parse import parse_qs

import nsgablack.catalog.facade as facade_mod
from nsgablack.catalog import (
    catalog_facets,
    catalog_neighbors,
    catalog_schema,
    catalog_source_info,
    catalog_summary,
    catalog_ui_snapshot,
    field_values,
    list_entries,
    search_entries,
    show_entry,
)
from nsgablack.catalog.registry import CatalogEntry
from nsgablack.catalog.dashboard import (
    _callback_focus_relation_group,
    _catalog_kind_arg,
    _build_deep_link_query,
    _deep_link_with_nav_action,
    _floating_nav_markup,
    _normalize_navigation_stack,
    _other_kind_hits,
    _ordered_kinds,
    _pick_default_kind,
    _read_query_params,
    _resolve_source_file,
    _selection_state,
    _view_state_key,
    build_streamlit_command,
)


def test_catalog_facets_surface_kind_specific_values():
    payload = catalog_facets(profile="framework-core", kind="adapter", query="vns")

    assert payload["kind"] == "adapter"
    assert payload["total"] >= 1
    assert "tags" in payload["facets"]
    assert any(item["value"] == "local_search" for item in payload["facets"]["tags"])


def test_catalog_neighbors_close_companion_loop():
    payload = catalog_neighbors("adapter.vns", profile="framework-core")

    assert payload is not None
    companion_keys = {item["key"] for item in payload["companions"]}
    assert "repr.context_gaussian" in companion_keys
    assert "repr.context_switch" in companion_keys
    relation_groups = payload.get("relation_groups", {})
    relation_chain_cards = tuple(payload.get("relation_chain_cards", ()) or ())
    assert "context_provides::mutation_sigma" in relation_groups
    assert "context_provides::vns_k" in relation_groups
    sigma_consumers = {item["key"] for item in relation_groups["context_provides::mutation_sigma"]}
    vns_consumers = {item["key"] for item in relation_groups["context_provides::vns_k"]}
    assert "repr.context_gaussian" in sigma_consumers
    assert "repr.context_switch" in vns_consumers
    assert any(
        str(card.get("family", "") or "") == "context"
        and str(card.get("value", "") or "") == "mutation_sigma"
        and int(card.get("outgoing_count", 0) or 0) >= 1
        for card in relation_chain_cards
    )


def test_catalog_ui_snapshot_returns_selected_entry():
    snapshot = catalog_ui_snapshot(
        profile="framework-core",
        kind="adapter",
        query="vns",
        selected_key="adapter.vns",
    )

    assert snapshot["selected"] is not None
    assert snapshot["selected"]["key"] == "adapter.vns"
    assert any(item["key"] == "adapter.vns" for item in snapshot["items"])


def test_framework_catalog_facade_routes_to_db_store(monkeypatch):
    class _FakeStore:
        def __init__(self):
            self.calls = []
            self.entry = CatalogEntry(
                key="adapter.vns",
                title="VNS",
                kind="adapter",
                import_path="nsgablack.adapters.vns:VNSAdapter",
                tags=("local_search",),
                summary="Variable neighborhood search.",
                companions=("repr.context_gaussian",),
                context_provides=("population",),
                use_when=("local refinement",),
            )

        def list_catalog_entries(self, **kwargs):
            self.calls.append(("list", kwargs))
            return [self.entry]

        def search_catalog_entries(self, query, **kwargs):
            self.calls.append(("search", {"query": query, **kwargs}))
            return [self.entry]

        def get_catalog_entry(self, key, **kwargs):
            self.calls.append(("show", {"key": key, **kwargs}))
            return self.entry if key == self.entry.key else None

        def facet_rows(self, **kwargs):
            self.calls.append(("facets", kwargs))
            return {"tags": [{"value": "local_search", "count": 1}]}

        def neighbor_payload(self, key, **kwargs):
            self.calls.append(("neighbors", {"key": key, **kwargs}))
            return {
                "key": key,
                "companions": [{"key": "repr.context_gaussian", "title": "Gaussian Context", "kind": "representation", "summary": ""}],
                "missing_companions": (),
                "linked_by": [],
                "relation_groups": {
                    "context_provides::population": [
                        {
                            "key": "repr.consumer",
                            "title": "PopulationConsumer",
                            "kind": "representation",
                            "summary": "",
                            "context_key": "population",
                            "relation_role": "consumer",
                        }
                    ]
                },
                "relation_labels": {
                    "context_provides::population": "产物 -> population -> 消费者",
                },
            }

    fake_store = _FakeStore()
    route = facade_mod.CatalogReadRoute(
        profile="framework-core",
        source_mode="prefer",
        effective_source="postgresql",
        db_store=fake_store,
        db_backend="postgresql",
        config_enabled=True,
    )
    monkeypatch.setattr(facade_mod, "_resolve_read_route", lambda **kwargs: route)

    listed = list_entries(profile="framework-core", scope="framework", kind="adapter")
    hits = search_entries("vns", profile="framework-core", scope="framework", kind="adapter")
    facets = catalog_facets(profile="framework-core", scope="framework", kind="adapter", fields=("tags",))
    neighbors = catalog_neighbors("adapter.vns", profile="framework-core", scope="framework")
    source = catalog_source_info(profile="framework-core", scope="framework")

    assert [entry.key for entry in listed] == ["adapter.vns"]
    assert [entry.key for entry in hits] == ["adapter.vns"]
    assert facets["facets"]["tags"][0]["value"] == "local_search"
    assert neighbors["companions"][0]["key"] == "repr.context_gaussian"
    assert source["effective_source"] == "postgresql"
    assert any(name == "list" for name, _ in fake_store.calls)
    assert any(name == "search" for name, _ in fake_store.calls)
    assert any(name == "facets" for name, _ in fake_store.calls)
    assert any(name == "neighbors" for name, _ in fake_store.calls)
    assert "context_provides::population" in neighbors["relation_groups"]


def test_preferred_db_entry_uses_installed_runtime_contracts(monkeypatch):
    stale = CatalogEntry(
        key="example.phi_bundle_image_search",
        title="PhiBundleImageSearch",
        kind="example",
        import_path=(
            "examples.cases.phi_bundle_image_search.cases.phi_bundle_image_search."
            "build_solver:build_phi_bundle_image_search_solver"
        ),
        context_provides=("phi_bundle_outer_search_records",),
    )

    class _FakeStore:
        def get_catalog_entry(self, key, **kwargs):
            _ = kwargs
            return stale if key == stale.key else None

    route = facade_mod.CatalogReadRoute(
        profile="default",
        source_mode="prefer",
        effective_source="postgresql",
        db_store=_FakeStore(),
        db_backend="postgresql",
        config_enabled=True,
    )
    monkeypatch.setattr(facade_mod, "_resolve_read_route", lambda **kwargs: route)

    entry = show_entry(stale.key, profile="default", scope="framework")

    assert entry is not None
    assert entry.context_provides == ()
    assert entry.artifact_provides == (
        "phi_bundle_outer_summary_json",
        "phi_bundle_outer_table_csv",
        "phi_bundle_outer_table_md",
    )


def test_catalog_schema_and_field_values_are_queryable():
    schema = catalog_schema(profile="framework-core", kind="adapter")
    tag_values = field_values("tags", profile="framework-core", kind="adapter", query="vns")
    hits = search_entries(
        "vns",
        profile="framework-core",
        kind="adapter",
        field_filters={"tags": ("local_search",)},
    )

    assert "companions" in schema["fields"]
    assert any(item["value"] == "local_search" for item in tag_values)
    assert any(entry.key == "adapter.vns" for entry in hits)


def test_dashboard_all_kind_helpers_and_global_bias_search():
    assert _catalog_kind_arg("all") is None
    assert _ordered_kinds(("plugin", "bias", "adapter"))[:4] == ("all", "adapter", "plugin", "bias")
    assert _pick_default_kind("all", ("all", "adapter", "bias")) == "all"

    snapshot = catalog_ui_snapshot(profile="framework-core", kind=None, query="bias", limit=12)

    assert snapshot["items"]
    assert any(str(item["key"]).startswith("bias.") for item in snapshot["items"])


def test_dashboard_suggests_other_kind_hits_for_bias_query():
    grouped = _other_kind_hits(
        query="bias",
        profile="framework-core",
        scope="framework",
        project_path=None,
        include_global=False,
        field="all",
        current_kind="adapter",
    )

    assert "bias" in grouped
    assert any(entry.key.startswith("bias.") for entry in grouped["bias"])


def test_floating_nav_markup_contains_top_and_selected_targets():
    active = _floating_nav_markup(locate_target="catalog-results-anchor", top_target="catalog-page-top")
    disabled = _floating_nav_markup(locate_target=None, top_target="catalog-page-top")

    assert "catalog-results-anchor" in active
    assert "catalog-page-top" in active
    assert "onclick=" in active
    assert "定位当前选中项" in active
    assert "回到页面顶部" in active
    assert "catalog-fab-disabled" in disabled


def test_deep_link_with_nav_action_appends_action_once():
    query = _build_deep_link_query(
        profile="framework-core",
        scope="framework",
        kind="adapter",
        query="vns",
        field="all",
        selected="adapter.vns",
        project_path="",
        include_global=False,
        db_path="",
        source_mode="",
        sort_by="title",
        sort_dir="desc",
        detail_tab="relations",
        open_relations="companions",
        column_mode="full",
        page_size=25,
        results_collapse="collapsed",
    )

    linked = _deep_link_with_nav_action(query, action="locate_selected")

    assert linked.count("nav_action=locate_selected") == 1
    params = parse_qs(linked.lstrip("?").split("#", 1)[0])
    assert params["nav_action"] == ["locate_selected"]
    assert params["selected"] == ["adapter.vns"] or params["selected"] == ["adapter:vns"]


def test_focus_relation_group_callback_updates_relation_view_state():
    class _FakeSt:
        def __init__(self):
            self.session_state = {}

    fake = _FakeSt()
    scope = "framework"
    kind = "adapter"
    open_key = _view_state_key(scope, kind, "open_relations")
    detail_key = _view_state_key(scope, kind, "detail_tab")
    fake.session_state[open_key] = ("companions",)

    _callback_focus_relation_group(
        fake,
        scope=scope,
        kind=kind,
        relation_group="context_provides::mutation_sigma",
    )

    assert fake.session_state[detail_key] == "relations"
    assert fake.session_state[open_key] == ("companions", "context_provides::mutation_sigma")
    assert fake.session_state["catalog_ui_pending_scroll_target"] == "catalog-detail-anchor"


def test_project_scope_catalog_snapshot_and_listing(tmp_path):
    root = tmp_path / "demo_project"
    root.mkdir()
    (root / ".case").write_text("kind = solver\n", encoding="utf-8")
    (root / "build_solver.py").write_text("def build_solver():\n    return None\n", encoding="utf-8")
    (root / "catalog" / "entries").mkdir(parents=True)
    (root / "catalog" / "entries" / "bias.toml").write_text(
        """[[entry]]
key = "bias.demo_local"
title = "DemoLocalBias"
kind = "bias"
import_path = "bias.demo_local:DemoLocalBias"
summary = "Project-local bias entry for dashboard tests."
tags = ["project", "demo", "local"]
""",
        encoding="utf-8",
    )

    info = catalog_source_info(scope="project", project_path=root)
    summary = catalog_summary(scope="project", project_path=root)
    entries = list_entries(scope="project", project_path=root, kind="bias", limit=None)
    snapshot = catalog_ui_snapshot(scope="project", project_path=root, kind="bias", selected_key="project.bias.demo_local")

    assert info["scope"] == "project"
    assert info["project_found"] is True
    assert info["project_root"] == str(root.resolve())
    assert summary["total"] == 1
    assert any(entry.key == "project.bias.demo_local" for entry in entries)
    assert snapshot["selected"] is not None
    assert snapshot["selected"]["key"] == "project.bias.demo_local"


def test_build_streamlit_command_includes_catalog_ui_arguments():
    command = build_streamlit_command(
        profile="framework-core",
        scope="project",
        kind="plugin",
        query="resume",
        field="usage",
        project_path="C:/tmp/demo_project",
        include_global=True,
        db_path="mysql://demo:secret@127.0.0.1:3306/nsgablack",
        source_mode="only",
        column_mode="full",
        page_size=25,
        results_collapse="collapsed",
        host="127.0.0.1",
        port=8601,
        headless=True,
    )

    assert command[:4] == ["python", "-m", "streamlit", "run"] or command[1:4] == ["-m", "streamlit", "run"]
    assert "--server.address" in command
    assert "--server.port" in command
    assert "--server.headless" in command
    assert "--profile" in command
    assert "--scope" in command
    assert "--kind" in command
    assert "--query" in command
    assert "--field" in command
    assert "--project-path" in command
    assert "--include-global" in command
    assert "--db-path" in command
    assert "mysql://demo:secret@127.0.0.1:3306/nsgablack" in command
    assert "--source-mode" in command
    assert "only" in command
    assert "--column-mode" in command
    assert "full" in command
    assert "--page-size" in command
    assert "25" in command
    assert "--results-collapse" in command
    assert "collapsed" in command


def test_selection_state_marks_hidden_selected_entry():
    items = [
        {"key": "adapter.vns", "title": "VNS"},
        {"key": "adapter.sa", "title": "SA"},
    ]

    visible = _selection_state("adapter.vns", items, selected_exists=True)
    hidden = _selection_state("adapter.nsga2", items, selected_exists=True)
    missing = _selection_state("adapter.unknown", items, selected_exists=False)

    assert visible["visible"] is True
    assert visible["row_index"] == 0
    assert hidden["hidden"] is True
    assert hidden["visible"] is False
    assert hidden["row_index"] is None
    assert missing["hidden"] is False


def test_dashboard_script_can_be_loaded_as_plain_script():
    module_path = Path(__file__).resolve().parents[1] / "catalog" / "dashboard.py"
    namespace = runpy.run_path(str(module_path))

    assert "build_streamlit_command" in namespace
    assert callable(namespace["build_streamlit_command"])


def test_current_selection_surface_contract_contains_prev_next_controls():
    source = (Path(__file__).resolve().parents[1] / "catalog" / "dashboard.py").read_text(encoding="utf-8")

    assert "Current Selection" in source
    assert "上一项" in source
    assert "下一项" in source
    assert "定位到结果区" in source
    assert "清除选中" in source


def test_deep_link_query_omits_internal_none_sentinel():
    query = _build_deep_link_query(
        profile="framework-core",
        scope="project",
        kind="plugin",
        query="resume",
        field="usage",
        selected="__none__",
        project_path="C:/tmp/demo_project",
        include_global=True,
        db_path="",
        source_mode="",
        sort_by="title",
        sort_dir="desc",
        detail_tab="relations",
        open_relations="companions,linked_by",
        column_mode="full",
        page_size=25,
        results_collapse="collapsed",
        field_filters={"tags": ("local_search", "demo")},
    )

    assert "profile=framework-core" in query
    assert "scope=project" in query
    assert "include_global=1" in query
    assert "sort_by=title" in query
    assert "sort_dir=desc" in query
    assert "detail_tab=relations" in query
    assert "open_relations=companions%2Clinked_by" in query
    assert "column_mode=full" in query
    assert "page_size=25" in query
    assert "results_collapse=collapsed" in query
    assert "f_tags=local_search%2Cdemo" in query
    assert "selected=" not in query


def test_navigation_stack_normalizer_keeps_valid_keys_only():
    stack = _normalize_navigation_stack(
        [
            {"key": "adapter.vns", "title": "VNS", "kind": "adapter"},
            {"key": "", "title": "ignore"},
            "bad",
        ]
    )

    assert stack == [{"key": "adapter.vns", "title": "VNS", "kind": "adapter"}]


def test_read_query_params_restores_base_and_field_filters():
    class _FakeStreamlit:
        query_params = {
            "profile": "framework-core",
            "scope": "project",
            "kind": "adapter",
            "query": "vns",
            "selected": "adapter.vns",
            "db_path": "mysql://demo",
            "source_mode": "prefer",
            "sort_by": "title",
            "sort_dir": "desc",
            "detail_tab": "relations",
            "open_relations": "companions,linked_by",
            "column_mode": "full",
            "page_size": "25",
            "results_collapse": "collapsed",
            "f_tags": "local_search,demo",
            "f_companions": "repr.context_gaussian",
        }

    base_params, field_filters = _read_query_params(_FakeStreamlit())

    assert base_params["profile"] == "framework-core"
    assert base_params["scope"] == "project"
    assert base_params["selected"] == "adapter.vns"
    assert base_params["db_path"] == "mysql://demo"
    assert base_params["source_mode"] == "prefer"
    assert base_params["sort_by"] == "title"
    assert base_params["sort_dir"] == "desc"
    assert base_params["detail_tab"] == "relations"
    assert base_params["open_relations"] == "companions,linked_by"
    assert base_params["column_mode"] == "full"
    assert base_params["page_size"] == "25"
    assert base_params["results_collapse"] == "collapsed"
    assert field_filters["tags"] == ("local_search", "demo")
    assert field_filters["companions"] == ("repr.context_gaussian",)


def test_deep_link_roundtrip_restores_result_layout_and_snapshot():
    original_query = _build_deep_link_query(
        profile="framework-core",
        scope="framework",
        kind="adapter",
        query="vns",
        field="usage",
        selected="adapter.vns",
        project_path="",
        include_global=False,
        db_path="mysql://demo",
        source_mode="prefer",
        sort_by="title",
        sort_dir="desc",
        detail_tab="relations",
        open_relations="companions,linked_by",
        column_mode="full",
        page_size=100,
        results_collapse="collapsed",
        field_filters={"tags": ("local_search",), "companions": ("repr.context_gaussian",)},
    )

    class _FakeStreamlit:
        query_params = {key: values[-1] for key, values in parse_qs(original_query.lstrip("?")).items()}

    base_params, field_filters = _read_query_params(_FakeStreamlit())
    rebuilt_query = _build_deep_link_query(
        profile=base_params["profile"],
        scope=base_params["scope"],
        kind=base_params["kind"],
        query=base_params["query"],
        field=base_params["field"],
        selected=base_params["selected"],
        project_path=base_params.get("project_path", ""),
        include_global=base_params.get("include_global", "") == "1",
        db_path=base_params.get("db_path", ""),
        source_mode=base_params.get("source_mode", ""),
        sort_by=base_params["sort_by"],
        sort_dir=base_params["sort_dir"],
        detail_tab=base_params["detail_tab"],
        open_relations=base_params["open_relations"],
        column_mode=base_params["column_mode"],
        page_size=int(base_params["page_size"]),
        results_collapse=base_params["results_collapse"],
        field_filters=field_filters,
    )
    snapshot = catalog_ui_snapshot(
        profile=base_params["profile"],
        scope=base_params["scope"],
        kind=base_params["kind"],
        query=base_params["query"],
        search_field=base_params["field"],
        field_filters=field_filters,
        selected_key=base_params["selected"],
    )

    assert parse_qs(rebuilt_query.lstrip("?")) == parse_qs(original_query.lstrip("?"))
    assert "db_path=mysql%3A%2F%2Fdemo" in rebuilt_query
    assert "source_mode=prefer" in rebuilt_query
    assert snapshot["selected"] is not None
    assert snapshot["selected"]["key"] == "adapter.vns"
    assert any(item["key"] == "adapter.vns" for item in snapshot["items"])


def test_resolve_source_file_finds_framework_module():
    path = _resolve_source_file("nsgablack.catalog.facade:catalog_summary")

    assert path is not None
    assert path.name == "facade.py"


def test_relation_chain_cards_use_collision_resistant_keys():
    source = (Path(__file__).resolve().parents[1] / "catalog" / "dashboard.py").read_text(encoding="utf-8")

    assert "catalog_ui::chain::open::{kind}::{family_key}::{card_index}" in source
    assert "catalog_ui::chain::jump::{kind}::{family_key}::{card_index}" in source
    assert "lane_group_id or lane_title" in source

