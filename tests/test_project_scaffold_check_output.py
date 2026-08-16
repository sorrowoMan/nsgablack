from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys

from nsgablack.project.scaffold import build_solver_check_payload, format_solver_check


class _Named:
    def __init__(self, name: str):
        self.name = name


class _Mediator:
    def list_providers(self):
        return (_Named("batch-provider"),)


def test_solver_check_reports_attached_components_and_safe_resource_context():
    pipeline = type(
        "Pipeline",
        (),
        {
            "initializer": _Named("initializer"),
            "mutator": _Named("mutator"),
            "repair": _Named("repair"),
        },
    )()
    solver = type(
        "Solver",
        (),
        {
            "problem": _Named("problem"),
            "adapter": _Named("adapter"),
            "representation_pipeline": pipeline,
            "evaluation_mediator": _Mediator(),
            "plugin_manager": type("Manager", (), {"plugins": (_Named("trace"),)})(),
        },
    )()

    payload = build_solver_check_payload(
        solver,
        resource_context={"device": "cpu", "threads": 2, "api_key": "not-for-output"},
    )

    assert payload["status"] == "assembly ok"
    assert payload["adapter"] == "adapter"
    assert payload["providers"] == ["batch-provider"]
    assert payload["plugins"] == ["trace"]
    assert payload["resource_context"] == {"device": "cpu", "threads": 2}
    rendered = format_solver_check(solver)
    assert json.loads(rendered.removeprefix("[check] "))["pipeline"] == "Pipeline"


def test_production_scheduling_check_does_not_create_run_artifacts(tmp_path):
    root = Path(__file__).resolve().parents[1]
    entry = (
        root
        / "examples"
        / "cases"
        / "production_scheduling"
        / "cases"
        / "production_scheduling"
        / "run_solver.py"
    )
    run_dir = tmp_path / "check-output-must-not-exist"

    completed = subprocess.run(
        [sys.executable, str(entry), "--check", "--run-dir", str(run_dir)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[check]" in completed.stdout
    assert not run_dir.exists()


def test_supply_adjustment_check_does_not_create_run_artifacts(tmp_path):
    root = Path(__file__).resolve().parents[1]
    entry = (
        root
        / "examples"
        / "cases"
        / "supply_adjustment_nested"
        / "cases"
        / "supply_adjustment_nested"
        / "run_solver.py"
    )
    run_dir = tmp_path / "check-output-must-not-exist"
    env = os.environ.copy()
    env["NSGABLACK_RESOURCE_CONTEXT_JSON"] = json.dumps(
        {
            "threads": 2,
            "namespace": "tests.supply",
            "grant": {"threads": 2, "workers": 2},
        }
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(entry),
            "--check",
            "--run-dir",
            str(run_dir),
            "--pop-size",
            "2",
            "--generations",
            "1",
            "--outer-parallel-workers",
            "4",
            "--inner-parallel-workers",
            "8",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[check]" in completed.stdout
    assert "threads=2 outer_workers=4->2 inner_workers=8->1" in completed.stdout
    assert "outer_backend=thread outer_workers=2 inner_backend=thread inner_workers=1" in completed.stdout
    assert not run_dir.exists()


def test_migrated_build_entries_are_assembly_only():
    root = Path(__file__).resolve().parents[1]
    entries = (
        root
        / "examples"
        / "cases"
        / "mlblack_symbolic_consensus_scaffold"
        / "cases"
        / "mlblack_symbolic_consensus_scaffold"
        / "build_solver.py",
        root
        / "examples"
        / "cases"
        / "supply_adjustment_nested"
        / "cases"
        / "supply_adjustment_nested"
        / "build_solver.py",
        root
        / "examples"
        / "cases"
        / "production_scheduling"
        / "cases"
        / "production_scheduling"
        / "build_solver.py",
    )

    for entry in entries:
        tree = ast.parse(entry.read_text(encoding="utf-8"), filename=str(entry))
        functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        assert "build_solver" in functions
        assert functions.isdisjoint({"main", "cli_main"}), entry


def test_shap_normal_run_reports_effective_project_resource_context():
    root = Path(__file__).resolve().parents[1]
    entry = root / "examples" / "cases" / "shap" / "cases" / "shap" / "run_solver.py"
    env = os.environ.copy()
    env["NSGABLACK_RESOURCE_CONTEXT_JSON"] = json.dumps(
        {
            "threads": 1,
            "namespace": "tests.shap.normal",
            "grant": {"threads": 1},
            "api_key": "must-not-leak",
        }
    )

    completed = subprocess.run(
        [sys.executable, str(entry), "--steps", "1"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    summaries = [line for line in completed.stdout.splitlines() if line.startswith("[resource-context] ")]
    assert len(summaries) == 1
    payload = json.loads(summaries[0].removeprefix("[resource-context] "))
    assert payload == {
        "grant": {"threads": 1},
        "namespace": "tests.shap.normal",
        "threads": 1,
    }
    assert "must-not-leak" not in completed.stdout
