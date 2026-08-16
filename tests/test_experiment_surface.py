import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from urllib.parse import parse_qs

from nsgablack.experiment.db import (
    experiment_db_candidate_targets,
    experiment_db_config_info,
    resolve_experiment_db_target,
    summarize_experiment_db_error,
)
from nsgablack.experiment import dashboard as experiment_dashboard
from nsgablack.experiment.dashboard import (
    _build_deep_link_query,
    _read_query_params,
    _sync_session_state_from_query,
    build_streamlit_command,
    dashboard_script_path,
)
from nsgablack.experiment.filesystem_surface import discover_filesystem_run_surfaces
from nsgablack.plugins import (
    list_runtime_artifact_surfaces,
    list_runtime_run_surfaces,
    runtime_surface_filter_values,
    runtime_surface_summary,
    show_runtime_artifact_surface,
    show_runtime_run_surface,
)


def _prepare_runtime_surface_db(sample_problem, sample_bias, tmp_path: Path) -> tuple[Path, str]:
    from nsgablack.adapters import SAConfig, SimulatedAnnealingAdapter
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.plugins import (
        ModuleReportConfig,
        ModuleReportPlugin,
        RuntimeSurfaceTrackerConfig,
        RuntimeSurfaceTrackerPlugin,
    )
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-10.0, high=10.0),
        mutator=ContextGaussianMutation(base_sigma=0.5, sigma_key="mutation_sigma"),
        repair=ClipRepair(low=-10.0, high=10.0),
    )
    solver = ComposableSolver(
        problem=sample_problem,
        adapter=SimulatedAnnealingAdapter(SAConfig(batch_size=6)),
        representation_pipeline=pipeline,
        bias_module=sample_bias,
    )

    db_path = tmp_path / "runtime_surface.sqlite3"
    solver.add_plugin(
        ModuleReportPlugin(
            config=ModuleReportConfig(
                output_dir=str(tmp_path),
                run_id="runtime_surface_cli_demo",
                write_bias_markdown=False,
            )
        )
    )
    solver.add_plugin(
        RuntimeSurfaceTrackerPlugin(
            config=RuntimeSurfaceTrackerConfig(
                db_path=str(db_path),
                namespace="ut_runtime_cli",
                tag="smoke",
            )
        )
    )
    solver.max_steps = 3
    result = solver.run()
    return db_path, str(result.get("run_id") or "")


def test_experiment_dashboard_command_builder() -> None:
    command = build_streamlit_command(
        db_path="runs/runtime_surface.sqlite3",
        limit=240,
        column_mode="full",
        page_size=25,
        results_collapse="collapsed",
        host="127.0.0.1",
        port=8607,
        headless=True,
    )

    assert command[:4] == [sys.executable, "-m", "streamlit", "run"]
    assert str(dashboard_script_path()) in command
    assert "--db" in command
    assert "runs/runtime_surface.sqlite3" in command
    assert "--limit" in command
    assert "240" in command
    assert "--column-mode" in command
    assert "full" in command
    assert "--page-size" in command
    assert "25" in command
    assert "--results-collapse" in command
    assert "collapsed" in command


def test_experiment_dashboard_uses_clickable_results_table() -> None:
    source = (Path(__file__).resolve().parents[1] / "experiment" / "dashboard.py").read_text(encoding="utf-8")
    assert 'on_select="rerun"' in source
    assert 'selection_mode="single-row"' in source
    assert "当前选中项 / Current Selection" in source
    assert "结果内快速切换 / Quick Selection" in source
    assert "按 selection_key 跳转 / Jump by selection_key" in source
    assert "上一项链接 / Previous Link" in source
    assert "下一项链接 / Next Link" in source


def test_experiment_dashboard_query_roundtrip() -> None:
    original_query = _build_deep_link_query(
        base_params={
            "db": "runs/runtime_surface.sqlite3",
            "limit": "180",
            "view": "artifact_catalog",
            "selected": "artifact:run_demo:modules_report_json",
            "detail_tab": "contracts",
            "column_mode": "full",
            "page_size": "25",
            "results_collapse": "collapsed",
            "query": "report",
        },
        field_filters={
            "artifact_role": "report",
            "artifact_producer_ref": "plugin:module_report",
            "run_screening_protocol": "target_corr+residual_gain+semantic_novelty+consensus_prior",
            "run_outer_search_protocol": "beam_basis_set_structure_search",
            "run_joint_core_score_min": "0.75",
        },
    )

    class _FakeStreamlit:
        query_params = {key: values[-1] for key, values in parse_qs(original_query.lstrip("?")).items()}

    base_params, field_filters = _read_query_params(_FakeStreamlit())
    rebuilt_query = _build_deep_link_query(base_params=base_params, field_filters=field_filters)

    assert parse_qs(rebuilt_query.lstrip("?")) == parse_qs(original_query.lstrip("?"))


def test_experiment_dashboard_query_selection_resets_stale_selection_widgets(monkeypatch) -> None:
    view_mode = "artifact_catalog"
    stale_key = "artifact:run_demo:old_report"
    selected_key = "artifact:run_demo:new_report"
    session_state = {
        "experiment_ui_last_query_signature": (("selected", stale_key),),
        f"experiment_ui_selection_hook::{view_mode}": stale_key,
        f"experiment_ui_selection_jump::{view_mode}": stale_key,
    }
    monkeypatch.setattr(
        experiment_dashboard,
        "st",
        type("FakeStreamlit", (), {"session_state": session_state})(),
    )

    restored_view = _sync_session_state_from_query(
        Namespace(
            db="runs/runtime_surface.sqlite3",
            limit=200,
            column_mode="full",
            page_size=20,
            results_collapse="collapsed",
        ),
        {
            "db": "runs/runtime_surface.sqlite3",
            "limit": "200",
            "view": view_mode,
            "selected": selected_key,
            "detail_tab": "contracts",
            "column_mode": "full",
            "page_size": "20",
            "results_collapse": "collapsed",
            "query": "report",
        },
        {"artifact_role": ("report",)},
    )

    assert restored_view == view_mode
    assert session_state["experiment_ui_selected"] == selected_key
    assert f"experiment_ui_selection_hook::{view_mode}" not in session_state
    assert f"experiment_ui_selection_jump::{view_mode}" not in session_state


def test_experiment_db_config_resolver_reads_toml_protocol(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "experiment_db.toml"
    config_path.write_text(
        "\n".join(
            [
                "[postgres]",
                "enabled = true",
                'mode = "prefer"',
                "readonly = false",
                'host = "127.0.0.1"',
                "port = 5432",
                'user = "postgres"',
                'password = "secret_pw"',
                'database = "nsgablack_runtime"',
                "connect_timeout = 12",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NSGABLACK_EXPERIMENT_DB_CONFIG", str(config_path))
    monkeypatch.delenv("NSGABLACK_EXPERIMENT_DB_URL", raising=False)
    monkeypatch.delenv("NSGABLACK_EXPERIMENT_DB_MODE", raising=False)
    monkeypatch.delenv("NSGABLACK_EXPERIMENT_DB_READONLY", raising=False)

    target = resolve_experiment_db_target()
    info = experiment_db_config_info()

    assert info["source"] == "file"
    assert info["db_backend"] == "postgresql"
    assert "nsgablack_runtime" in target
    assert target.startswith("postgresql://postgres:secret_pw@127.0.0.1:5432/")


def test_experiment_db_candidate_targets_include_local_sqlite_fallback(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = runs_dir / "runtime_surface.sqlite3"
    sqlite_path.write_text("", encoding="utf-8")
    config_path = tmp_path / "experiment_db.toml"
    config_path.write_text(
        "\n".join(
            [
                "[postgres]",
                "enabled = true",
                'mode = "prefer"',
                'host = "127.0.0.1"',
                "port = 5432",
                'user = "postgres"',
                'password = "secret_pw"',
                'database = "nsgablack_runtime"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NSGABLACK_EXPERIMENT_DB_CONFIG", str(config_path))
    monkeypatch.delenv("NSGABLACK_EXPERIMENT_DB_URL", raising=False)

    explicit_default = resolve_experiment_db_target()
    candidates = experiment_db_candidate_targets(explicit_default)

    assert candidates[0].startswith("postgresql://postgres:secret_pw@127.0.0.1:5432/")
    assert str(sqlite_path.resolve()) in candidates


def test_experiment_db_error_summary_masks_mojibake_auth_detail() -> None:
    exc = RuntimeError(
        'connection failed: connection to server at "127.0.0.1", port 5432 failed: '
        'FATAL: password authentication failed for user "postgres"'
    )

    summary = summarize_experiment_db_error(exc, target="postgresql://postgres:secret_pw@localhost:5432/nsgablack")

    assert summary["code"] == "auth_failed"
    assert "password authentication failed" in summary["detail"].lower()
    assert "***" in summary["safe_target"]


def test_discover_filesystem_run_surfaces_reads_standard_run_files(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "demo.modules.json").write_text(
        (
            "{\n"
            '  "solver": {"class": "ComposableSolver"},\n'
            '  "adapter": {"class": "SimulatedAnnealingAdapter"},\n'
            '  "plugins": [{"name": "module_report"}, {"name": "runtime_surface_tracker"}]\n'
            "}\n"
        ),
        encoding="utf-8",
    )
    (runs_dir / "demo.bias.json").write_text('{"enabled": false}', encoding="utf-8")
    (runs_dir / "demo.csv").write_text(
        "run_id,step,elapsed_s,eval_count,best_score\n"
        "demo,3,0.15,18,1.25\n",
        encoding="utf-8",
    )

    rows = discover_filesystem_run_surfaces(root=runs_dir, query="simulated", limit=20)

    assert len(rows) == 1
    row = rows[0]
    assert row["run_id"] == "demo"
    assert row["solver_class"] == "ComposableSolver"
    assert row["adapter_class"] == "SimulatedAnnealingAdapter"
    assert "module_report" in row["plugin_names"]
    assert row["last_step"] == "3"
    assert row["last_best_score"] == "1.25"


def test_runtime_surface_queries_gracefully_handle_missing_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "empty_runtime_surface.sqlite3"

    summary = runtime_surface_summary(db_path)

    assert summary["tables"]["runtime_run_surface"] == 0
    assert summary["tables"]["runtime_artifact_surface"] == 0
    assert list_runtime_run_surfaces(db_path, limit=20) == []
    assert list_runtime_artifact_surfaces(db_path, limit=20) == []
    assert show_runtime_run_surface(db_path, run_id="missing_run") is None
    assert show_runtime_artifact_surface(
        db_path,
        run_id="missing_run",
        artifact_id="missing_artifact",
    ) is None


def test_plugin_gallery_demo_materializes_runtime_surface_example(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "runtime_surface_example.sqlite3"

    proc = subprocess.run(
        [
            sys.executable,
            "examples/_misc_examples/plugin_gallery_demo.py",
            "--steps",
            "4",
            "--plugins",
            "plugin.module_report",
            "--runtime-db",
            str(db_path),
            "--runtime-namespace",
            "ut.plugin_gallery",
            "--runtime-tag",
            "smoke",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "runtime surface db:" in proc.stdout
    summary = runtime_surface_summary(db_path)
    filter_values = runtime_surface_filter_values(db_path)
    assert summary["tables"]["runtime_run_surface"] == 1
    assert summary["tables"]["runtime_artifact_surface"] >= 1
    assert "run_screening_protocol" in filter_values
    assert "run_outer_search_protocol" in filter_values
    assert "run_structure_head" in filter_values
    assert "run_search_input_space" in filter_values
    assert "run_pool_expansion_unit" in filter_values
    assert "run_gradient_guidance_mode" in filter_values
    assert "run_basis_binding_mode" in filter_values
    assert "run_escape_policy" in filter_values


def test_cli_experiment_surface_summary_and_queries(sample_problem, sample_bias, tmp_path: Path) -> None:
    db_path, run_id = _prepare_runtime_surface_db(sample_problem, sample_bias, tmp_path)
    assert run_id
    root = Path(__file__).resolve().parents[1]

    summary_proc = subprocess.run(
        [sys.executable, "-m", "nsgablack", "experiment", "summary", "--db", str(db_path)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert summary_proc.returncode == 0, summary_proc.stderr
    assert '"runtime_run_surface": 1' in summary_proc.stdout
    assert '"runtime_artifact_surface":' in summary_proc.stdout

    summary_default_proc = subprocess.run(
        [sys.executable, "-m", "nsgablack", "experiment", "summary"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "NSGABLACK_EXPERIMENT_DB_URL": str(db_path)},
    )
    assert summary_default_proc.returncode == 0, summary_default_proc.stderr
    assert '"runtime_run_surface": 1' in summary_default_proc.stdout

    list_runs_proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "nsgablack",
            "experiment",
            "list-runs",
            "--db",
            str(db_path),
            "--status",
            "ok",
            "--limit",
            "10",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert list_runs_proc.returncode == 0, list_runs_proc.stderr
    assert '"surface_kind": "solver"' in list_runs_proc.stdout
    assert '"driver_ref": "adapter:' in list_runs_proc.stdout

    show_run_proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "nsgablack",
            "experiment",
            "show-run",
            "--db",
            str(db_path),
            "--run-id",
            run_id,
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert show_run_proc.returncode == 0, show_run_proc.stderr
    assert '"run_id":' in show_run_proc.stdout
    assert '"assembly_record_json":' in show_run_proc.stdout

    list_artifacts_proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "nsgablack",
            "experiment",
            "list-artifacts",
            "--db",
            str(db_path),
            "--artifact-role",
            "report",
            "--limit",
            "20",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert list_artifacts_proc.returncode == 0, list_artifacts_proc.stderr
    assert '"artifact_role": "report"' in list_artifacts_proc.stdout

    show_artifact_proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "nsgablack",
            "experiment",
            "show-artifact",
            "--db",
            str(db_path),
            "--run-id",
            run_id,
            "--artifact-id",
            "modules_report_json",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert show_artifact_proc.returncode == 0, show_artifact_proc.stderr
    assert '"artifact_id": "modules_report_json"' in show_artifact_proc.stdout




