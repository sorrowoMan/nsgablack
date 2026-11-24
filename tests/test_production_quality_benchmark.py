"""The quality harness selects formal groups and uses one shared report scale."""
from __future__ import annotations

import csv
import importlib
import json
import os
from pathlib import Path
import sys

import numpy as np
import pytest

from examples.cases.production_scheduling.cases.production_scheduling.problem.production_problem import ProductionConstraints, ProductionSchedulingProblem
from examples.cases.production_scheduling.cases.production_scheduling.refactor_data import ProductionData

benchmark = importlib.import_module("examples.cases.production_scheduling.run_quality_benchmark")


def flags(argv):
    return {key: argv[index + 1] for index, key in enumerate(argv[:-1])
            if key.startswith("--") and not argv[index + 1].startswith("--")}


def test_quality_groups_have_explicit_real_data_and_finite_single_cpu_grants():
    groups = benchmark.quality_groups(benchmark.ALGORITHMS, benchmark.SEEDS)
    assert len(groups) == len(set(groups)) == 12
    previous = os.environ.get(benchmark.SESSION_ENV)
    plan = benchmark.quality_plan("contract-test", groups)
    assert os.environ.get(benchmark.SESSION_ENV) == previous
    for row in plan:
        stage = row["stage"]
        assert stage["mode"] == "build"
        assert stage["timeout_seconds"] == 900
        assert stage["resource_requests"]["production_scheduling"] == {"threads": 1, "gpus": 0, "backend": "local"}
        argv = stage["component_overrides"]["production_scheduling"]["argv"]
        values = flags(argv)
        assert [values[name] for name in ("--machines", "--materials", "--days")] == ["22", "157", "31"]
        assert values["--max-evaluations"] == "2500"
        assert "--single-objective" not in argv  # Baseline chooses it inside its existing builder.
        assert Path(values["--export"]).is_relative_to(benchmark.ROOT / "results" / "quality" / "contract-test")
        if "directional" in row["group"]:
            assert values["--quality-cycles"] == "2"
            assert values["--refine-directions"] == "8"


def test_original_smoke_group_is_retained_and_pilot_is_a_separate_group():
    with benchmark._session("contract-test"):
        config = benchmark.runpy.run_path(str(benchmark.ROOT / "project_config.py"))
    assert config["GROUPS"]["default"] == {"stages": ["main"]}
    main = next(stage for stage in config["STAGES"] if stage["name"] == "main")
    smoke = flags(main["component_overrides"]["production_scheduling"]["argv"])
    assert smoke["--machines"] == "4" and smoke["--materials"] == "10" and smoke["--generations"] == "1"
    pilot = benchmark.quality_plan("contract-test", ["quality_pilot_s42"])[0]
    values = flags(pilot["stage"]["component_overrides"]["production_scheduling"]["argv"])
    assert values["--max-evaluations"] == "300"
    assert values["--quality-cycles"] == "1"
    assert values["--refine-directions"] == "4"


def test_group_filter_and_plan_do_not_start_a_solver(monkeypatch, capsys):
    def no_execution(*args, **kwargs):
        raise AssertionError("plan must not execute a Project")
    monkeypatch.setattr(benchmark, "supervise_project", no_execution)
    assert benchmark.main(["--groups", "directional", "--seeds", "43", "--run-id", "plan-only", "--plan"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [row["group"] for row in payload["runs"]] == ["quality_directional_s43"]
    with pytest.raises(ValueError):
        benchmark.quality_plan("../other", ["quality_directional_s43"])
    with pytest.raises(ValueError):
        benchmark.quality_groups(["unregistered"], [42])


def _write_schedule(path, schedule):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Day_Index", "Date", *[f"Machine{i}" for i in range(22)]])
        for day in range(31):
            writer.writerow([day, f"Day{day+1}", *schedule[:, day].astype(int).tolist()])


def test_cross_algorithm_recommendations_share_one_global_original_objective_scale(tmp_path, monkeypatch):
    data = ProductionData(machines=22, materials=1, days=31,
        bom_matrix=np.ones((22, 1), dtype=bool), supply_matrix=np.full((1, 31), 100000.0),
        machine_weights=np.ones(22))
    problem = ProductionSchedulingProblem(data, ProductionConstraints(max_machines_per_day=8,
        min_machines_per_day=5, min_production_per_machine=50,
        max_production_per_machine=10000, include_penalty_objective=False))
    monkeypatch.setattr(benchmark, "ROOT", tmp_path)
    monkeypatch.setattr(benchmark, "_audit_problem", lambda: problem)
    folder = tmp_path / "results" / "quality" / "test"
    names = ["quality_phased_s42", "quality_directional_s42", "quality_greedy_s42"]
    schedules = [np.zeros((22, 31)), np.zeros((22, 31)), np.zeros((22, 31))]
    schedules[0][0] = 100
    schedules[0][0, 0] = 2000
    schedules[1][0] = 130
    schedules[2][:8] = 200  # One global dominating plan must not erase other arms' axes.
    for name, schedule in zip(names, schedules):
        _write_schedule(folder / name / "exports" / "plan.csv", schedule)
    state = {"run_id": "test", "inputs": {"raw_model_sha256": "test"}, "runs": [
        {"group": name, "status": "succeeded", "project_run_id": "formal-"+name,
         "elapsed_seconds": 3.0, "formal": {"evaluations": 100}} for name in names]}
    summary = benchmark.aggregate_results(folder, state)
    global_bounds = summary["global_policies"]["balanced"]["normalization_bounds"]
    assert global_bounds is not None
    for name in names:
        selected = summary["by_group"][name]["policies"]["balanced"]
        assert selected["normalization_bounds"] == global_bounds
        assert selected["normalization_source"] == "explicit shared reference"
    assert all(len(report["raw_objectives"]) == 4 for report in summary["reports"])
    assert (folder / "comparison.json").is_file() and (folder / "comparison.csv").is_file()
    assert sorted(path.name for path in (folder / "recommendations").iterdir()) == ["balanced.csv", "production.csv", "stability.csv"]


def test_owned_project_supervisor_enforces_timeout_without_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "ROOT", tmp_path)
    result = benchmark.supervise_project([sys.executable, "-c", "import time; time.sleep(5)"],
        tmp_path / "bounded.log", os.environ.copy(), timeout_seconds=0.1)
    assert result["failure"] == "project_hard_timeout"
    assert result["exit_code"] != 0
    assert result["elapsed_seconds"] < 4


def test_report_only_rejects_a_csv_changed_after_the_recorded_run(tmp_path, monkeypatch):
    import hashlib
    monkeypatch.setattr(benchmark, 'ROOT', tmp_path)
    folder = tmp_path / 'results' / 'quality' / 'recorded'
    csv_path = folder / 'exports' / 'plan.csv'
    csv_path.parent.mkdir(parents=True)
    csv_path.write_text('original bytes', encoding='utf-8')
    (folder / 'comparison.json').write_text(json.dumps({'reports': [{
        'csv_file': str(csv_path.relative_to(tmp_path)),
        'csv_sha256': hashlib.sha256(csv_path.read_bytes()).hexdigest()}]}), encoding='utf-8')
    benchmark._verify_existing_export_hashes(folder)
    csv_path.write_text('changed bytes', encoding='utf-8')
    with pytest.raises(ValueError, match='recorded experiment bytes'):
        benchmark._verify_existing_export_hashes(folder)
