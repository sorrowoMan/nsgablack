from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs

import pytest

from nsgablack.catalog import dashboard, facade, registry
from nsgablack.catalog.registry import Catalog, CatalogEntry


def _forbidden(*args, **kwargs):
    raise AssertionError("Hosted Catalog reached a local project, database, or source-file capability")


@pytest.fixture
def hosted_source(monkeypatch):
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.delenv("NSGABLACK_CATALOG_HOSTED_SOURCE", raising=False)
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "only")
    entry = CatalogEntry(
        key="tool.safe", title="Safe", kind="tool", import_path="builtins:len",
        summary="解池查询", config_keys=("none",), minimal_wiring=("len(())",),
        contract={"catalog": {"role": "selector", "concepts": ["解池"],
                              "operations": ["select"], "boundaries": ["只读选择"]}},
    )
    source = Catalog([entry], details_resolved=True)
    monkeypatch.setattr(facade, "get_source_catalog", lambda **kwargs: source)
    monkeypatch.setattr(registry, "_CATALOG_BY_PROFILE", {})
    monkeypatch.setattr(facade, "resolve_catalog_store", _forbidden)
    monkeypatch.setattr(facade, "load_project_catalog", _forbidden)
    from nsgablack.project import catalog as project_catalog
    from nsgablack.catalog.providers.mysql_provider import MySQLCatalogProvider
    from nsgablack.catalog.providers.postgres_provider import PostgresCatalogProvider
    from nsgablack.catalog.store import mysql, postgres

    monkeypatch.setattr(project_catalog, "project_import_context", _forbidden)
    monkeypatch.setattr(MySQLCatalogProvider, "load", _forbidden)
    monkeypatch.setattr(PostgresCatalogProvider, "load", _forbidden)
    monkeypatch.setattr(mysql, "mysql_config_enabled", lambda: True)
    monkeypatch.setattr(postgres, "postgres_config_enabled", lambda: True)
    return entry


def _unsafe_link_options():
    return dict(
        profile="framework-core", scope="project", kind="tool", query="解池", field="usage",
        selected="tool.safe", project_path="C:/private/project", include_global=True,
        db_path="postgresql://reader:secret@example.invalid/catalog", source_mode="only",
        sort_by="title", sort_dir="asc", detail_tab="source", open_relations="companions",
        column_mode="standard", page_size=25, results_collapse="expanded",
        field_filters={"concepts": ("解池",), "role": ("selector",)},
    )


def test_hosted_overrides_url_and_restored_session_before_first_read(monkeypatch, hosted_source):
    st = SimpleNamespace(
        sidebar=SimpleNamespace(radio=lambda *args, **kwargs: None, markdown=lambda *args, **kwargs: None),
        query_params={"scope": "project", "project_path": "C:/private/url",
                      "db_path": "mysql://reader:secret@example.invalid/catalog", "source_mode": "only",
                      "include_global": "1", "query": "解池", "f_concepts": "解池"},
        session_state={"catalog_ui_scope": "project", "catalog_ui_project_path": "C:/private/session",
                       "catalog_ui_db_path": "postgresql://private/session", "catalog_ui_include_global": True,
                       "catalog_ui_source_mode": "only"},
    )
    monkeypatch.setattr(dashboard, "_require_streamlit", lambda: st)
    monkeypatch.setattr(dashboard, "_set_page_config", lambda value: None)
    monkeypatch.setattr(dashboard, "_inject_style", lambda value: None)

    class FirstReadComplete(Exception):
        pass

    def first_read(profile, scope, project_path, include_global, db_path, source_mode):
        assert (scope, project_path, include_global, db_path, source_mode) == ("framework", "", False, "", "off")
        assert dashboard._load_summary(profile, scope, project_path, include_global, db_path, source_mode)["total"] == 1
        raise FirstReadComplete

    monkeypatch.setattr(dashboard, "_cached_summary", first_read)
    with pytest.raises(FirstReadComplete):
        dashboard.run_dashboard(["--scope", "project", "--db-path", "mysql://private/cli"])
    assert "project_path" not in st.query_params
    assert "db_path" not in st.query_params
    assert st.query_params["f_concepts"] == "解池"
    assert st.session_state["catalog_ui_scope"] == "framework"
    assert st.session_state["catalog_ui_db_path"] == ""


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_every_hosted_loader_uses_registry_even_with_database_only_configuration(hosted_source, profile):
    args = (profile, "project", "C:/private/project", True)
    db_args = ("mysql://reader:secret@example.invalid/catalog", "only")
    source_info = dashboard._load_source_info(*args, *db_args)
    assert source_info["scope"] == "framework"
    assert source_info["project_root"] is None
    assert source_info["source_mode"] == "off"
    assert dashboard._load_summary(*args, *db_args)["total"] == 1
    assert dashboard._load_schema(*args, *db_args)["scope"] == "framework"
    facets = dashboard._load_facets(*args, "tool", "", "all", *db_args)
    assert facets["facets"]["concepts"] == [{"value": "解池", "count": 1}]
    for query in ("", "解池"):
        rows = dashboard._load_items(*args, "tool", query, "all", (("role", ("selector",)),), *db_args)
        assert tuple(row["key"] for row in rows) == (hosted_source.key,)
    assert dashboard._load_selected_entry(*args, hosted_source.key, *db_args)["role"] == "selector"
    assert dashboard._load_neighbors(*args, hosted_source.key, *db_args)["scope"] == "framework"
    hits = dashboard._other_kind_hits(query="解池", profile=profile, scope="project", project_path="C:/private",
                                      include_global=True, field="all", current_kind="adapter",
                                      db_path=db_args[0], source_mode="only")
    assert hits["tool"][0].key == hosted_source.key


def test_hosted_links_and_url_updates_drop_sensitive_sources(hosted_source):
    options = _unsafe_link_options()
    st = SimpleNamespace(query_params={})
    dashboard._write_query_params(st, **options)
    for payload in (st.query_params, dashboard._query_param_payload(**options),
                    {key: values[-1] for key, values in parse_qs(dashboard._build_deep_link_query(**options)[1:]).items()}):
        assert "project_path" not in payload
        assert "db_path" not in payload
        assert "include_global" not in payload
        assert payload["scope"] == "framework"
        assert payload["source_mode"] == "off"
        assert payload["f_concepts"] == "解池"
        assert payload["f_role"] == "selector"
        assert payload["profile"] == "framework-core"


class _SourceView:
    def __init__(self):
        self.session_state = {}
        self.output = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def columns(self, spec):
        return [self] * len(spec)

    def markdown(self, value, **kwargs):
        self.output.append(str(value))

    code = markdown
    caption = markdown
    json = markdown

    def expander(self, label, **kwargs):
        self.output.append(label)
        return self

    def text_input(self, label, *, value, **kwargs):
        self.output.append(value)
        return value

    def button(self, label, **kwargs):
        self.output.append(label)
        return False


@pytest.mark.parametrize("tab", ["overview", "interface", "source"])
def test_hosted_detail_does_not_resolve_or_open_server_files(monkeypatch, hosted_source, tab):
    monkeypatch.setattr(dashboard, "_resolve_source_file", _forbidden)
    monkeypatch.setattr(dashboard, "_open_source_file", _forbidden)
    monkeypatch.setattr(dashboard, "_reveal_source_file", _forbidden)
    view = _SourceView()
    dashboard._render_detail(
        view, entry=dashboard._entry_detail_payload(hosted_source), neighbors=None,
        source_info={"project_root": "C:/private/project"}, deep_link_query="?scope=framework",
        scope="framework", kind="tool", detail_tab=tab, expanded_relation_groups=(),
    )
    output = "\n".join(view.output)
    assert "C:/private" not in output
    assert "打开 Source File" not in output
    assert "定位到 Source File" not in output
    if tab == "source":
        assert "builtins:len" in output


def test_hosted_source_helpers_fail_closed_even_when_called_directly(monkeypatch, hosted_source):
    monkeypatch.setattr(dashboard.importlib.util, "find_spec", _forbidden)
    monkeypatch.setattr(dashboard.subprocess, "Popen", _forbidden)
    assert dashboard._resolve_source_file("private.module:Secret", project_root="C:/private") is None
    assert dashboard._open_source_file(Path(__file__)) is False
    assert dashboard._reveal_source_file(Path(__file__)) is False


def test_local_mode_keeps_source_options_and_links(monkeypatch):
    monkeypatch.delenv("NSGABLACK_CATALOG_HOSTED", raising=False)
    st = SimpleNamespace(session_state={"catalog_ui_scope": "project"})
    dashboard._enforce_hosted_session(st)
    assert st.session_state["catalog_ui_scope"] == "project"
    options = dashboard._catalog_source_options("project", "C:/project", True, "mysql://host/db", "only")
    assert options == {"scope": "project", "project_path": "C:/project", "include_global": True,
                       "db_path": "mysql://host/db", "source_mode": "only"}
    params = parse_qs(dashboard._build_deep_link_query(**_unsafe_link_options())[1:])
    assert params["project_path"] == ["C:/private/project"]
    assert params["db_path"] == ["postgresql://reader:secret@example.invalid/catalog"]


def test_hosted_database_source_is_server_configured_and_not_exposed(monkeypatch):
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED_SOURCE", "database")
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_URL", "mysql://trusted:private@db/catalog")
    options = dashboard._catalog_source_options("project", "private", True, "mysql://evil/db", "off")
    assert options == dict(scope="framework", project_path=None, include_global=False, db_path=None, source_mode="only")
    observed = []
    monkeypatch.setattr(dashboard, "catalog_summary", lambda **kw: observed.append(kw) or {"total": 279})
    assert dashboard._load_summary("default", "project", "private", True, "mysql://evil/db", "off")["total"] == 279
    assert observed[0]["source_mode"] == "only" and observed[0]["db_path"] is None
    params = dashboard._public_query_params(dict(db_path="mysql://evil/db", project_path="private"))
    assert params["source_mode"] == "only" and params["db_path"] == ""
    assert "trusted" not in str(params) and "private" not in str(params)


@pytest.mark.parametrize("source", ["database", "unknown"])
def test_hosted_database_missing_or_invalid_configuration_fails_closed(monkeypatch, source):
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED_SOURCE", source)
    monkeypatch.delenv("NSGABLACK_CATALOG_DB_URL", raising=False)
    with pytest.raises(RuntimeError):
        dashboard._catalog_source_options("framework", None, False, None, "off")
