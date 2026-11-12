"""The standard Case consumes GA's named elite through normal Pool tasks."""
from __future__ import annotations

from pathlib import Path
import shutil

import numpy as np
import pytest

from blackbase.project import build_case, load_case_builder, run_case
from blackbase.resources import ResourceAllocator, ResourceContext, ResourceRequest
from nsgablack.core.state.solution_pool import SolutionRef
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin


SMALL_ELITE = {"population_size": 6, "ga_steps": 2, "local_steps": 2,
               "local_batch": 1, "refinement_source": "elite", "elite_count": 2,
               "evaluation_budget": 20}


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    source = Path(__file__).resolve().parents[1] / "examples" / "cases" / "assembled_ga_vns"
    target = tmp_path_factory.mktemp("assembled_ga_vns_elite") / "project"
    shutil.copytree(source, target,
        ignore=shutil.ignore_patterns("results", "__pycache__", ".blackbase", "*.pyc"))
    return target


@pytest.fixture
def grant():
    allocator = ResourceAllocator()
    lease = allocator.acquire(ResourceRequest(threads=1, workers=1),
        owner_id="assembled_elite", scope="optimization")
    resource = ResourceContext.from_mapping(lease.resource_context(namespace="assembled_elite"))
    try:
        yield resource
    finally:
        allocator.release(lease)


def build(project, grant, options):
    return build_case(load_case_builder(project, "hybrid_search"), resource_context=grant,
                      component_overrides={"config": options})


def record_evaluations(monkeypatch, solver):
    calls = []
    evaluate = solver.problem.evaluate
    def observed(candidate):
        calls.append(np.array(candidate, copy=True))
        return evaluate(candidate)
    monkeypatch.setattr(solver.problem, "evaluate", observed)
    return calls


def trace_plugin(solver):
    return next(item for item in solver.plugin_manager.list_plugins() if item.name == "committed_trace")


def refs(values):
    return tuple(SolutionRef.from_dict(value) for value in values)


def test_default_population_source_keeps_native_selector_and_original_configuration(project, grant):
    default = build(project, grant, {})
    assert default.adapter.cfg.phase_schedule == (("ga", 8), ("vns", 72), ("return", 1))
    assert default.adapter.cfg.total_batch_size == 252
    assert default.adapter.units[0].adapter.inner.cfg.population_size == 12
    assert default.adapter.units[0].adapter.inner.get_bound_selector() is None
    solver = build(project, grant, {"population_size": 4, "ga_steps": 1,
        "local_steps": 2, "local_batch": 1, "evaluation_budget": 20})
    assert solver.adapter.units[0].adapter.inner.get_bound_selector() is None
    run_case(solver)
    assert solver.run_progress_steps == 10 and solver.evaluation_count == 20
    assert not solver.solution_pool.has_subpool("ga_elite")


def test_ga_named_elite_is_frozen_consumed_and_returned_without_hidden_evaluation(project, grant, monkeypatch):
    solver = build(project, grant, SMALL_ELITE)
    calls = record_evaluations(monkeypatch, solver)
    ga = solver.adapter.units[0].adapter.inner
    delivered = []
    update = ga.update
    def observe_update(control, candidates, feedback, context):
        delivered.append(np.array(candidates, copy=True))
        return update(control, candidates, feedback, context)
    monkeypatch.setattr(ga, "update", observe_update)
    run_case(solver)
    assert solver.resource_binding_audit["current"] is True
    assert solver.run_progress_steps == 7
    assert solver.evaluation_count == len(calls) == 20
    assert solver.evaluation_budget_reserved == 0 and solver.evaluation_batch_allowance(1) == 0
    records = trace_plugin(solver).records
    assert [row["phase"] for row in records] == ["ga", "ga", "vns", "vns", "vns", "vns", "return"]
    ga_end, first_vns, returned = records[1], records[2], records[-1]
    seeds = refs(ga_end["elite"]["refs"])
    assert len(seeds) == 2 and set(seeds).issubset(refs(ga_end["ga_member_refs"]))
    assert first_vns["frozen_refinement_refs"] == ga_end["elite"]["refs"]
    values = solver.read_solutions(seeds).numeric_matrix
    np.testing.assert_array_equal(calls[12], values[0])
    np.testing.assert_array_equal(calls[14], values[1])
    # The VNS never edits GA members. Only the final ordinary GA.update sees
    # all admitted refinement proposals and performs population competition.
    assert all(row["ga_member_refs"] == ga_end["ga_member_refs"] for row in records[2:6])
    assert [len(batch) for batch in delivered] == [6, 6, 4]
    aggregate = refs(returned["aggregate_return"]["refs"])
    assert len(aggregate) == 4  # Two baselines plus two neighborhoods, not two final winners.
    np.testing.assert_array_equal(delivered[-1], solver.read_solutions(aggregate).numeric_matrix)
    np.testing.assert_array_equal(calls[16:], delivered[-1])
    assert returned["source_raw_unchanged"] is True
    raw, violations = solver.solution_pool.read_raw_feedback(seeds)
    np.testing.assert_array_equal(raw, ga_end["elite"]["raw_objectives"])
    np.testing.assert_array_equal(violations, ga_end["elite"]["raw_violations"])
    np.testing.assert_allclose(raw[:, 0], np.sum((values - [2., -1.]) ** 2, axis=1))
    assert len(ga.get_population_solution_refs(solver)) == len(ga.algorithm_unit.member_age) == 6
    select = solver.adapter.units[1].adapter.spec.select
    before = len(calls), solver.evaluation_count
    assert select(solver, {}) == solver.solution_pool.subpool_refs("ga_elite")
    assert before == (len(calls), solver.evaluation_count)


def test_elite_handoff_checkpoint_resumes_frozen_inputs_and_matches_continuation(project, grant, tmp_path, monkeypatch):
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "assembled-elite-handoff-resume")
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path / "checkpoints"),
        save_every=3, save_on_finish=False, strict=True)
    source = build(project, grant, SMALL_ELITE)
    original_calls = record_evaluations(monkeypatch, source)
    source.add_plugin(CheckpointResumePlugin(config=config))
    run_case(source)
    checkpoint, = tuple((tmp_path / "checkpoints").glob("*_g000002_*.pkl"))
    source_records = trace_plugin(source).records
    frozen = source_records[2]["frozen_refinement_refs"]
    saved_evaluations = source_records[2]["evaluations"]

    restored = build(project, grant, SMALL_ELITE)
    restored_calls = record_evaluations(monkeypatch, restored)
    initializer = restored.adapter.units[0].adapter.inner.get_bound_initializer()
    def no_new_initialization(*args, **kwargs):
        raise AssertionError("resuming VNS must not regenerate the GA population")
    monkeypatch.setattr(initializer, "initialize", no_new_initialization)
    reader = CheckpointResumePlugin(config=config)
    restored.add_plugin(reader)
    assert reader.resume(str(checkpoint))
    run_case(restored)
    assert restored.run_progress_steps == 7 and restored.evaluation_count == 20
    assert len(restored_calls) == 20 - saved_evaluations
    np.testing.assert_array_equal(restored_calls, original_calls[saved_evaluations:])
    assert trace_plugin(restored).records[2]["frozen_refinement_refs"] == frozen
    assert trace_plugin(restored).records[-1]["source_raw_unchanged"] is True
    left, right = source.adapter.units[0].adapter.inner, restored.adapter.units[0].adapter.inner
    np.testing.assert_array_equal(left.population, right.population)
    np.testing.assert_array_equal(left.objectives, right.objectives)
    np.testing.assert_array_equal(left.algorithm_unit.member_age, right.algorithm_unit.member_age)
    np.testing.assert_array_equal(source.read_solutions(refs(frozen)).numeric_matrix,
                                  restored.read_solutions(refs(frozen)).numeric_matrix)
