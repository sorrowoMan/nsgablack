import sys


def test_unified_ui_command_builder() -> None:
    from nsgablack.ui.dashboard import build_streamlit_command, dashboard_script_path

    command = build_streamlit_command(
        surface="experiment",
        profile="framework-core",
        scope="project",
        kind="plugin",
        query="runtime",
        field="usage",
        project_path="C:/tmp/demo_project",
        include_global=True,
        db_path="postgresql://catalog_demo",
        source_mode="only",
        experiment_db="postgresql://runtime_demo",
        limit=240,
        column_mode="full",
        page_size=25,
        results_collapse="collapsed",
        host="127.0.0.1",
        port=8611,
        headless=True,
    )

    assert command[:4] == [sys.executable, "-m", "streamlit", "run"]
    assert str(dashboard_script_path()) in command
    assert "--surface" in command
    assert "experiment" in command
    assert "--profile" in command
    assert "framework-core" in command
    assert "--db-path" in command
    assert "postgresql://catalog_demo" in command
    assert "--experiment-db" in command
    assert "postgresql://runtime_demo" in command
    assert "--limit" in command
    assert "240" in command


def test_cli_unified_ui_launch(monkeypatch):
    from nsgablack.__main__ import main
    from nsgablack.ui import dashboard as ui_dashboard

    seen = {}

    def fake_launch_ui_dashboard(**kwargs):
        seen.update(kwargs)
        return 0

    monkeypatch.setattr(ui_dashboard, "launch_ui_dashboard", fake_launch_ui_dashboard)

    code = main(
        [
            "ui",
            "--surface",
            "catalog",
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
            "--db-path",
            "postgresql://catalog_demo",
            "--source-mode",
            "only",
            "--experiment-db",
            "postgresql://runtime_demo",
            "--limit",
            "180",
            "--column-mode",
            "full",
            "--page-size",
            "25",
            "--results-collapse",
            "collapsed",
            "--host",
            "127.0.0.1",
            "--port",
            "8608",
            "--headless",
        ]
    )

    assert code == 0
    assert seen == {
        "surface": "catalog",
        "profile": "framework-core",
        "scope": "project",
        "kind": "plugin",
        "query": "resume",
        "field": "usage",
        "project_path": "C:/tmp/demo_project",
        "include_global": True,
        "db_path": "postgresql://catalog_demo",
        "source_mode": "only",
        "experiment_db": "postgresql://runtime_demo",
        "limit": 180,
        "column_mode": "full",
        "page_size": 25,
        "results_collapse": "collapsed",
        "host": "127.0.0.1",
        "port": 8608,
        "headless": True,
    }


def test_unified_ui_surface_inference() -> None:
    from nsgablack.ui.dashboard import _infer_surface

    assert _infer_surface({"profile": "framework-core", "kind": "adapter"}, "home") == "catalog"
    assert _infer_surface({"db": "runs/runtime.sqlite3", "view": "run_catalog"}, "home") == "experiment"
    assert _infer_surface({"selected": "artifact:demo_run:report_json"}, "home") == "experiment"
    assert _infer_surface({}, "home") == "home"
