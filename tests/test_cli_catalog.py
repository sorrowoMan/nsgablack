from __future__ import annotations


def test_cli_catalog_search_smoke(capsys):
    from nsgablack.__main__ import main

    code = main(["catalog", "search", "vns"])
    assert code == 0
    out = capsys.readouterr().out
    assert "adapter.vns" in out


def test_cli_catalog_add_upsert(tmp_path, capsys):
    from nsgablack.__main__ import main

    target = tmp_path / "entries.toml"
    code = main(
        [
            "catalog",
            "add",
            "--file",
            str(target),
            "--key",
            "bias.demo_cli",
            "--title",
            "DemoCliBias",
            "--kind",
            "bias",
            "--import-path",
            "nsgablack.bias.domain.constraint:ConstraintBias",
            "--summary",
            "Domain bias: demo from CLI",
            "--tags",
            "bias,demo",
            "--context-requires",
            "population_ref,generation",
            "--context-provides",
            "bias_score",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "catalog entry upserted: bias.demo_cli" in out
    text = target.read_text(encoding="utf-8")
    assert "key = 'bias.demo_cli'" in text
    assert "use_when = [" in text
    assert "minimal_wiring = [" in text
    assert "example_entry = " in text
    assert "context_requires = ['population_ref', 'generation']" in text
    assert "context_provides = ['bias_score']" in text


def test_cli_catalog_ui_launch(monkeypatch):
    from nsgablack.__main__ import main
    from nsgablack.catalog import dashboard as dashboard_mod

    seen = {}

    def fake_launch_catalog_dashboard(**kwargs):
        seen.update(kwargs)
        return 0

    monkeypatch.setattr(dashboard_mod, "launch_catalog_dashboard", fake_launch_catalog_dashboard)

    code = main(
        [
            "catalog",
            "ui",
            "--profile",
            "framework-core",
            "--scope",
            "project",
            "--kind",
            "plugin",
            "--query",
            "resume",
            "--field",
            "usage",
            "--project-path",
            "C:/tmp/demo_project",
            "--include-global",
            "--host",
            "127.0.0.1",
            "--port",
            "8602",
            "--headless",
        ]
    )

    assert code == 0
    assert seen == {
        "profile": "framework-core",
        "scope": "project",
        "kind": "plugin",
        "query": "resume",
        "field": "usage",
        "project_path": "C:/tmp/demo_project",
        "include_global": True,
        "db_path": None,
        "source_mode": None,
        "column_mode": "standard",
        "page_size": 50,
        "results_collapse": "expanded",
        "host": "127.0.0.1",
        "port": 8602,
        "headless": True,
    }


def test_cli_catalog_ui_accepts_all_kind(monkeypatch):
    from nsgablack.__main__ import main
    from nsgablack.catalog import dashboard as dashboard_mod

    seen = {}

    def fake_launch_catalog_dashboard(**kwargs):
        seen.update(kwargs)
        return 0

    monkeypatch.setattr(dashboard_mod, "launch_catalog_dashboard", fake_launch_catalog_dashboard)

    code = main(["catalog", "ui", "--profile", "framework-core", "--kind", "all", "--query", "bias"])

    assert code == 0
    assert seen["kind"] == "all"
    assert seen["query"] == "bias"


def test_cli_catalog_materialize_calls_sql_materializer(monkeypatch, capsys):
    from nsgablack.__main__ import main
    import nsgablack.catalog as catalog_mod

    seen = {}

    def fake_materialize_catalog_to_db(**kwargs):
        seen.update(kwargs)
        return {"backend": "postgresql", "components": 3, "contexts": 3, "usages": 3, "params": 5, "methods": 6, "health": 3}

    monkeypatch.setattr(catalog_mod, "materialize_catalog_to_db", fake_materialize_catalog_to_db)

    code = main(["catalog", "materialize", "--profile", "framework-core", "--runtime", "--db-url", "postgresql://demo"])

    assert code == 0
    assert seen == {"profile": "framework-core", "runtime": True, "db_url": "postgresql://demo"}
    out = capsys.readouterr().out
    assert "catalog postgresql materialized" in out


def test_cli_catalog_cleanup_legacy_postgres_dry_run(monkeypatch, capsys):
    from nsgablack.__main__ import main
    import nsgablack.catalog as catalog_mod

    seen = {}

    def fake_cleanup_postgres_legacy_catalog(**kwargs):
        seen.update(kwargs)
        return {
            "backend": "postgresql",
            "cleanup_needed": True,
            "cleanup_candidates": ["catalog_component", "catalog_context_contract"],
            "can_execute": True,
            "executed": False,
        }

    monkeypatch.setattr(catalog_mod, "cleanup_postgres_legacy_catalog", fake_cleanup_postgres_legacy_catalog)

    code = main(
        [
            "catalog",
            "cleanup-legacy-postgres",
            "--profile",
            "framework-core",
            "--db-url",
            "postgresql://demo",
        ]
    )

    assert code == 0
    assert seen == {"profile": "framework-core", "db_url": "postgresql://demo", "execute": False}
    out = capsys.readouterr().out
    assert "catalog postgresql legacy cleanup dry-run" in out
    assert "catalog_component" in out


def test_cli_catalog_cleanup_legacy_postgres_requires_yes(capsys):
    from nsgablack.__main__ import main

    code = main(["catalog", "cleanup-legacy-postgres", "--execute"])

    assert code == 2
    err = capsys.readouterr().err
    assert "--yes" in err


def test_cli_catalog_export_relations(monkeypatch, capsys):
    from nsgablack.__main__ import main
    import nsgablack.catalog as catalog_mod

    seen = {}

    def fake_export_catalog_relations(**kwargs):
        seen.update(kwargs)
        return {
            "profile": "framework-core",
            "scope": "framework",
            "summary": {"total_nodes": 2, "total_edges": 1},
            "written_files": {"table-csv": "C:/tmp/out.table.csv"},
        }

    monkeypatch.setattr(catalog_mod, "export_catalog_relations", fake_export_catalog_relations)

    code = main(
        [
            "catalog",
            "export-relations",
            "--profile",
            "framework-core",
            "--scope",
            "framework",
            "--kind",
            "adapter",
            "--query",
            "vns",
            "--field",
            "usage",
            "--format",
            "json",
            "--format",
            "key-csv",
            "--format",
            "mermaid",
            "--format",
            "family-dot",
            "--format",
            "family-mermaid",
            "--output",
            "out/demo_relations",
        ]
    )

    assert code == 0
    assert seen == {
        "output_path": "out/demo_relations",
        "formats": ["json", "key-csv", "mermaid", "family-dot", "family-mermaid"],
        "profile": "framework-core",
        "scope": "framework",
        "project_path": None,
        "include_global": False,
        "kind": "adapter",
        "query": "vns",
        "search_field": "usage",
        "db_path": None,
        "source_mode": None,
    }
    out = capsys.readouterr().out
    assert "catalog relation export completed" in out
