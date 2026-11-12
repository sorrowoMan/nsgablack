from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from blackbase.resources import ResourceContext
from benchmarks.transparency_core import ProblemMeter, compare, run_pair
from benchmarks.transparency_costs import cost_spec, measure, production_spec


def test_cpu_calibration_extends_sample_past_coarse_clock_ticks(monkeypatch):
    from benchmarks import transparency_costs as module
    ticks = iter([0., 0., 0., .05, 0., .2])
    counts = []
    monkeypatch.setattr(module.time, "process_time", lambda: next(ticks))
    monkeypatch.setattr(module, "_cpu_work", lambda n: counts.append(n))
    assert module.calibrate_cpu(1) == 41
    assert counts == [100, 2048, 4096, 8192]


@pytest.mark.parametrize("mode", ["full", "no_step_trace", "lean"])
def test_trace_modes_match_reference_without_changing_evaluations(mode):
    spec = cost_spec(0, size=5, steps=3)
    result = measure(spec, 11, mode, context=ResourceContext(namespace="cost_unit", grant={"threads":1}), checkpoint=lambda:None)
    assert result["status"] == "passed", result
    assert result["evaluations"] == 15
    assert result["normal"]["commits"] == 2 and result["normal"]["evaluations"] == 10
    assert result["normal"]["wall_s"]["framework_repair"] > 0
    if mode != "full":
        assert result["observer_self_time"]["wall_s"] == 0


def test_lean_meter_counts_calls_without_retaining_candidates():
    meter = ProblemMeter(cost_spec(0).make_problem(), record_calls=False)
    for _ in range(4):
        meter.evaluate(np.zeros(8))
    assert meter.call_count == meter.summary()["calls"] == 4
    assert meter.records == []


def test_injected_cost_changes_no_objective_or_constraints():
    base = cost_spec(0).make_problem()
    other = cost_spec(.1).make_problem()
    candidate = np.full(8, .25)
    np.testing.assert_array_equal(base.evaluate(candidate), other.evaluate(candidate))
    np.testing.assert_array_equal(base.evaluate_constraints(candidate), other.evaluate_constraints(candidate))
    with pytest.raises(ValueError):
        cost_spec(float("nan"))


def test_real_production_uses_original_data_and_recovers_without_reevaluation(tmp_path):
    context = ResourceContext(namespace="production_cost_unit", grant={"threads":1,"workers":1})
    spec = production_spec(context, size=5, steps=3)
    assert spec.metadata["dimension"] == 22 * 31
    assert spec.metadata["synthetic_fallback"] is False
    problem = spec.make_problem()
    before = problem.data.supply_matrix.copy()
    repair_owner = spec.make_pipeline(11).problem_repair.operation.__self__
    repair_supply = repair_owner.supply_matrix.copy()
    result = run_pair(spec, 11, work_dir=tmp_path)
    for key in ("semantics", "quality", "recovery"):
        assert result[key]["status"] == "passed", result[key]
    np.testing.assert_array_equal(before, problem.data.supply_matrix)
    np.testing.assert_array_equal(repair_supply, repair_owner.supply_matrix)


@pytest.mark.parametrize("mode", ["full", "lean"])
def test_parent_cancellation_remains_connected_when_trace_is_disabled(mode):
    from blackbase.resources import CancellationRequested
    spec = cost_spec(0, size=5, steps=3)
    calls = []
    original = spec.make_problem
    def problem_factory():
        problem = original()
        evaluate = problem.evaluate
        def evaluated(x):
            calls.append(1)
            return evaluate(x)
        problem.evaluate = evaluated
        return problem
    from benchmarks.transparency_core import build_pair_solver
    def checkpoint():
        if len(calls) >= 3:
            raise CancellationRequested("cancel-cost-check")
    solver, meter, trace, _ = build_pair_solver(replace(spec, make_problem=problem_factory), 11,
        capture_trace=mode=="full", record_calls=mode=="full", runtime_checkpoint=checkpoint)
    with pytest.raises(CancellationRequested, match="cancel-cost-check"):
        solver.run(max_steps=3)
    assert len(calls) == meter.call_count == solver.evaluation_count == 3
    assert trace.commits == 0


@pytest.mark.parametrize("capture", [True, False])
def test_trace_modes_keep_sqlite_budget_and_checkpoint_accounting(tmp_path, capture):
    from tests.test_shared_evaluation_budget import _runtime
    from benchmarks.transparency_core import build_pair_solver
    from blackbase.resources import SQLiteBudgetAuthority
    runtime = _runtime(tmp_path, limit=1000)
    lease = runtime.acquire_case("cost-budget")
    context = runtime.resource_context(lease, case_name="cost-budget")
    spec = cost_spec(0, size=5, steps=3)
    def build():
        return build_pair_solver(spec, 11, resource_context=context, checkpoint_dir=tmp_path / "checkpoints",
                                 capture_trace=capture, record_calls=capture)
    try:
        full, meter, _, _ = build()
        full.run(max_steps=3)
        prefix, _, _, writer = build()
        prefix.run(max_steps=1)
        path = writer.save_checkpoint(reason="cost-prefix")
        resumed, resumed_meter, _, reader = build()
        assert reader.resume(str(path))
        resumed.run(max_steps=3)
        assert compare(spec.project(full), spec.project(resumed)) is None
        assert resumed_meter.call_count == 10 and resumed.evaluation_count == 15
        authority = runtime.budget_authority
        reopened = SQLiteBudgetAuthority(authority.path, namespace=authority.namespace, scope=authority.scope)
        status = reopened.status("evaluations")
        assert status.committed == 30 and status.reserved == 0
    finally:
        runtime.release(lease)
        runtime.close()
