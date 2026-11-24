"""Exercise an actual VNS neighbor inside a three-level standard Case run."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

import numpy as np
import pytest

from blackbase.project import execute_project
from blackbase.types import SolverResult


@pytest.mark.parametrize("improving", [False, True], ids=["native-neighbor", "improving-neighbor"])
def test_inner_neighbor_keeps_local_identity_and_updates_outer_score(tmp_path, improving):
    source = (Path(__file__).resolve().parents[1] / "examples" / "cases"
              / "super_topology_orchestration")
    project = tmp_path / "project"
    shutil.copytree(source, project,
        ignore=shutil.ignore_patterns(".blackbase", "__pycache__", "*.pyc"))
    # The shipped smoke profile runs only the baseline. One further local
    # commit exercises mutation, admission and selection within the existing
    # child evaluation budget of two; the Trainer's budget of three also fits.
    inner_entry = project / "cases" / "inner_solver" / "solver" / "case.py"
    content = inner_entry.read_text(encoding="utf-8-sig")
    original_call = "self.solver.run(max_steps=1, max_step_attempts=3)"
    assert content.count(original_call) == 1
    inner_entry.write_text(content.replace(original_call,
        "self.solver.run(max_steps=2, max_step_attempts=3)"), encoding="utf-8")
    if improving:
        # Bind an ordinary change through the real VNS seam. This moves the
        # fixed smoke initializer toward all nine calibration targets, so the
        # test also covers returning a selected successor rather than merely
        # retaining the baseline after a worse native neighbor.
        adapter_entry = project / "cases" / "inner_solver" / "adapter" / "main.py"
        adapter_source = adapter_entry.read_text(encoding="utf-8-sig")
        original_adapter = "return VNSAdapter(VNSConfig(batch_size=1, k_max=1, base_sigma=0.15))"
        assert adapter_source.count(original_adapter) == 1
        adapter_source = adapter_source.replace(
            "import VNSAdapter, VNSConfig", "import VNSAdapter, VNSConfig, ChangeResult")
        adapter_source = adapter_source.replace(original_adapter,
            "return VNSAdapter(VNSConfig(batch_size=1, k_max=1, base_sigma=0.15), change=advance)")
        adapter_source += ("\n\ndef advance(request, *, rng):\n"
                           "    return ChangeResult(request.candidate + 0.15)\n")
        adapter_entry.write_text(adapter_source, encoding="utf-8")

    result = execute_project(project, run_id="triple-nested-neighbor", record=True)
    assert result.ok
    outer_result = result.case_results[-1]
    audit = SolverResult.from_dict(outer_result.output).metadata["super_topology"]
    assert all(audit["invariants"].values())
    assert audit["candidate_trainer_calls"] == 9
    outer = audit["solution_pool"]
    assert outer["committed_steps"] == 4 and outer["evaluation_count"] == 9
    expected_rows = []
    observations = []
    pool_ids = {outer["pool_id"]}
    for record in audit["nested_calls"]:
        trainer = record["trainer_pool"]
        inner = record["inner"]["inner_pool"]
        pool_ids.update((trainer["pool_id"], inner["pool_id"]))
        assert trainer["committed_steps"] == 1 and trainer["evaluation_count"] == 1
        assert inner["committed_steps"] == 2 and inner["evaluation_count"] == 2

        members = inner["members"]
        assert inner["evidence_complete"] and len(members) == 2
        assert [item["stamp"]["generation"] for item in members] == [0, 1]
        assert members[0]["ref"]["candidate_token"] != members[1]["ref"]["candidate_token"]
        values = np.asarray([item["values"] for item in members])
        assert values.shape == (2, 1)
        assert not np.array_equal(values[0], values[1])
        assert members[1]["parent_token"] == members[0]["ref"]["candidate_token"]
        point = np.asarray(record["candidate"], dtype=float)
        target = float(np.clip(.5 * (point[0] - point[1]), -1., 1.))
        raw = np.asarray([item["raw_objectives"] for item in members])
        violations = np.asarray([item["raw_violation"] for item in members])
        np.testing.assert_allclose(raw[:, 0], (values[:, 0] - target) ** 2)
        np.testing.assert_array_equal(violations, np.zeros(2))
        calibration = float(record["inner"]["selected_calibration"])
        assert (calibration - target) ** 2 == pytest.approx(float(raw.min()))
        if improving:
            assert raw[1, 0] < raw[0, 0]
            assert calibration == pytest.approx(float(values[1, 0]))
        assert record["inner"]["calibration_target"] == pytest.approx(target)
        expected = np.asarray([
            (point[0] - .65) ** 2 + (point[1] - .25) ** 2
            + .2 * (calibration - target) ** 2,
            point[0] ** 2 + .5 * point[1],
        ])
        np.testing.assert_allclose(record["objectives"], expected)
        trainer_raw = [item["raw_objectives"] for item in trainer["members"]]
        np.testing.assert_allclose(trainer_raw, [expected])
        expected_rows.append((*point, *expected))

        inner_usage = record["inner"]["inner_budget_usage"]["evaluations"]
        trainer_usage = record["trainer_budget_usage"]["evaluations"]
        assert inner_usage["charged_to_parent"] == 2
        assert inner_usage["returned_to_parent"] == 0
        assert trainer_usage["charged_to_parent"] == 3
        assert trainer_usage["returned_to_parent"] == 0
        assert inner_usage["settlement_status"] == trainer_usage["settlement_status"] == "settled"
        assert inner["pool_id"] != outer["pool_id"]
        observations.append({"target": target, "candidates": values.tolist(),
            "raw_objectives": raw.tolist(), "selected_calibration": calibration,
            "outer_candidate": point.tolist(), "outer_objectives": expected.tolist()})

    # Every dynamic invocation owns its local mutable search state, even
    # though all calls participate in the same Project and budget lineage.
    assert len(pool_ids) == 19
    outer_values = np.asarray([item["values"] for item in outer["members"]])
    outer_raw = np.asarray([item["raw_objectives"] for item in outer["members"]])
    np.testing.assert_allclose(sorted(map(tuple, np.column_stack((outer_values, outer_raw)))),
                               sorted(expected_rows))
    summary = {"status": "passed", "improving_operation": improving,
        "outer_steps": 4, "outer_evaluations": 9,
        "trainer_evaluations": 9, "inner_evaluations": 18, "local_pools": 19,
        "observations": observations}
    (project / "pool_validation.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
