"""故障验证使用实际 Project SQLite 预算，不借本地计数假装持久化。"""
from copy import deepcopy
from dataclasses import replace

import numpy as np

import pytest

from benchmarks.transparency_faults import run_fault_checks


def _specs():
    from benchmarks.transparency_trajectory import specs as trajectory_specs
    from benchmarks.transparency_population import specs as population_specs
    from benchmarks.transparency_structured import specs as structured_specs
    from benchmarks.transparency_composition import specs as composition_specs
    return {spec.name: spec for factory in (trajectory_specs, population_specs, structured_specs, composition_specs)
            for spec in factory()}


@pytest.mark.parametrize("name", ("sa", "mas", "nsga2_zdt1", "bayesian_optimization", "search_plan_nested"))
def test_real_update_fault_rolls_back_search_but_preserves_sqlite_cost_and_evidence(name, tmp_path):
    report = run_fault_checks(_specs()[name], seed=11, work_dir=tmp_path)
    assert report["status"] == "passed", report
    assert len(report["modes"]) == 2
    for mode in report["modes"]:
        assert all(mode["checks"].values()), mode
        evidence = mode["evidence"]
        assert evidence["committed_steps_before_fault"] == 1
        assert evidence["failed_attempt_evaluations"] > 0
        assert evidence["sqlite_budget_committed"] == evidence["evaluations_after_fault"]
        assert evidence["sqlite_budget_reserved"] == 0
        assert evidence["event_status"] == "failed" and evidence["event_phase"] == "finalized"
        assert evidence["restored_problem_calls"] == evidence["restored_new_commits"] == 0


def test_harness_reports_broken_adapter_rollback_as_failure(tmp_path):
    spec = _specs()["sa"]
    original_factory = spec.make_adapter

    def broken_adapter(seed):
        adapter = original_factory(seed)
        adapter.restore_step_state = lambda state: None
        return adapter

    report = run_fault_checks(replace(spec, make_adapter=broken_adapter), seed=11, work_dir=tmp_path)
    assert report["status"] == "failed", report
    assert any(row["status"] == "failed" for row in report["modes"])


def test_fault_output_requires_explicit_artifact_directory():
    with pytest.raises(ValueError, match="work_dir"):
        run_fault_checks(_specs()["sa"])


def test_mas_fitted_model_step_rollback_uses_runtime_codec_and_restores_predictions(monkeypatch):
    from benchmarks.transparency_core import build_pair_solver, compare
    solver, _, _, _ = build_pair_solver(_specs()["mas"], 11)
    solver.setup()
    assert solver.step().committed and solver.step().committed
    adapter = solver.adapter
    assert adapter._surrogate_is_fitted()
    before = deepcopy(adapter.get_state())
    prediction = adapter._surrogate.predict(np.asarray([[0., 0.], [1., -1.]]))
    unit_id = adapter.algorithm_unit.unit_id

    def forbidden(*args, **kwargs):
        pytest.fail("native MAS step rollback must not call the persistent Unit codec")

    monkeypatch.setattr(type(adapter.unit_binding), "restore", forbidden)
    update = adapter.update

    def fail(control, candidates, feedback, context):
        update(control, candidates, feedback, context)
        raise RuntimeError("MAS update finished before fault")

    monkeypatch.setattr(adapter, "update", fail)
    with pytest.raises(RuntimeError, match="MAS update finished") as caught:
        solver.step()
    assert not getattr(caught.value, "step_rollback_errors", ())
    assert compare(before, adapter.get_state()) is None
    assert adapter.algorithm_unit.unit_id == unit_id
    np.testing.assert_allclose(adapter._surrogate.predict(np.asarray([[0., 0.], [1., -1.]])), prediction)


@pytest.mark.parametrize("runtime_snapshot", [True, False])
def test_mas_history_validation_is_preserved_for_runtime_and_portable_state(runtime_snapshot, monkeypatch):
    from benchmarks.transparency_core import build_pair_solver
    solver, _, _, _ = build_pair_solver(_specs()["mas"], 11)
    solver.setup()
    assert solver.step().committed
    adapter = solver.adapter
    state = adapter.snapshot_step_state() if runtime_snapshot else adapter.get_state()
    state["history_x"] = [[999., 888.]]

    def forbidden(*args, **kwargs):
        pytest.fail("contradictory history must be rejected before rebuilding the model")

    monkeypatch.setattr(adapter, "_restore_surrogate_from_history", forbidden)
    restore = adapter.restore_step_state if runtime_snapshot else adapter.set_state
    with pytest.raises(ValueError, match="history disagrees"):
        restore(state)
