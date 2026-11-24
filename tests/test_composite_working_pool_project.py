"""A standard Project inherits one Chain working area through its nested Router."""
from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import pytest

from blackbase.participation import ParticipationContract
from blackbase.project import build_case, load_case_builder, run_case
from blackbase.resources import ResourceAllocator, ResourceContext, ResourceRequest
from nsgablack.adapters import StrategyChainAdapter, StrategyRouterAdapter
from nsgablack.core.state.solution_pool import SolutionRef
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.plugins.base import Plugin


WORKSPACE = "search_workspace"


class OutsideWorkspaceSeed(Plugin):
    """One additional root seed proves that a working area is not global main."""
    participation = ParticipationContract()
    state_recovery_level = "L1"
    state_recovery_notes = "Restores the seed receipt without generating another candidate."
    context_notes = ("Uses the normal Pipeline initializer once, without evaluation.",)

    def __init__(self):
        super().__init__(name="outside_workspace_seed")
        self.run_id, self.ref = None, None

    def on_solver_init(self, solver):
        if self.run_id == solver.run_session.run_id and self.ref is not None:
            return
        if solver.run_session.resume_loaded:
            raise ValueError("restored outside-seed receipt is missing")
        before = set(solver.solution_pool.select(stage="initial"))
        solver.init_population(1, solver.build_context())
        added = tuple(ref for ref in solver.solution_pool.select(stage="initial") if ref not in before)
        if len(added) != 1:
            raise ValueError("the test source must create exactly one initial candidate")
        self.run_id, self.ref = solver.run_session.run_id, added[0]

    def get_state(self):
        return {"schema": "working_pool_project.outside_seed/v1", "run_id": self.run_id,
                "ref": None if self.ref is None else self.ref.as_dict()}

    def set_state(self, state):
        if not isinstance(state, Mapping) or state.get("schema") != "working_pool_project.outside_seed/v1":
            raise ValueError("invalid outside-seed checkpoint")
        self.run_id = state.get("run_id")
        self.ref = None if state.get("ref") is None else SolutionRef.from_dict(state["ref"])


@pytest.fixture
def project(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "examples" / "cases" / "pool_workflow_pilot"
    root = tmp_path / "project"
    shutil.copytree(source, root,
        ignore=shutil.ignore_patterns("results", "__pycache__", ".blackbase", "*.pyc"))
    path = root / "cases" / "ga_partition" / "config.py"
    data = path.read_text(encoding="utf-8-sig")
    for before, after in (("source_count: int = 100", "source_count: int = 30"),
            ("population_size: int = 100", "population_size: int = 30"),
            ("offspring_size: int = 80", "offspring_size: int = 10"),
            ("working_pool: str | None = None", f'working_pool: str | None = "{WORKSPACE}"')):
        assert before in data
        data = data.replace(before, after, 1)
    path.write_text(data, encoding="utf-8")
    for name in ("pool_source", "workflow_trace"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    return root


@pytest.fixture
def grant():
    allocator = ResourceAllocator()
    lease = allocator.acquire(ResourceRequest(threads=1, workers=1),
        owner_id="working_pool_project", scope="optimization")
    resource = ResourceContext.from_mapping(lease.resource_context(namespace="working_pool_project"))
    try:
        yield resource
    finally:
        allocator.release(lease)


def build(project, grant):
    solver = build_case(load_case_builder(project, "ga_partition"), resource_context=grant)
    outside = OutsideWorkspaceSeed()
    solver.add_plugin(outside, after=("pipeline_source", "workflow_trace"))
    return solver, outside


def record_evaluations(solver, monkeypatch):
    calls = []
    evaluate = solver.problem.evaluate
    def observed(candidate):
        calls.append(np.array(candidate, copy=True))
        return evaluate(candidate)
    monkeypatch.setattr(solver.problem, "evaluate", observed)
    return calls


def leaf(solver):
    chain = solver.adapter
    assert isinstance(chain, StrategyChainAdapter)
    router, = chain.step_transaction_children()
    assert isinstance(router, StrategyRouterAdapter)
    worker = router.units[0].adapter
    assert worker.spec.select is None  # No copied source declaration on the child.
    return worker.inner


def refs(values):
    return tuple(SolutionRef.from_dict(value) for value in values)


def assert_committed_workspace(solver, outside):
    pool = solver.solution_pool
    initial = pool.subpool_refs("reference")
    accepted = pool.select(stage="accepted")
    assert len(initial) == 30 and len(pool.select(stage="initial")) == 31
    assert outside.ref not in initial
    assert pool.subpool_metadata(WORKSPACE)["published"] is True
    # This region retains initial references and all admitted trials. It is
    # deliberately larger than the population's selected 30 members.
    assert pool.subpool_refs(WORKSPACE) == (*initial, *accepted)
    assert outside.ref not in pool.subpool_refs(WORKSPACE)
    assert len(accepted) == 50 and len(leaf(solver).get_population_solution_refs(solver)) == 30
    intake = tuple(SolutionRef.from_dict(item["metadata"]["solution_source_ref"])
                   for item in pool.read_provenance(accepted[:30]))
    assert intake == initial
    assert solver.resource_binding_audit["current"] is True
    assert solver.run_progress_steps == 3 and solver.evaluation_count == 50
    assert solver.evaluation_budget_reserved == 0 and solver.evaluation_batch_allowance(1) == 0


def test_standard_case_inherits_chain_workspace_and_keeps_root_seed_outside(project, grant, monkeypatch):
    solver, outside = build(project, grant)
    calls = record_evaluations(solver, monkeypatch)
    run_case(solver)
    assert len(calls) == 50
    assert_committed_workspace(solver, outside)
    report = json.loads((project / "results" / "ga_partition.json").read_text(encoding="utf-8"))
    assert report["working_pool"] == WORKSPACE
    assert len(report["initial"]["working_pool"]["refs"]) == 30
    assert [len(row["working_pool"]["refs"]) for row in report["records"]] == [60, 70, 80]
    assert [row["evaluations"] for row in report["records"]] == [30, 40, 50]


def test_standard_working_area_checkpoint_restores_membership_without_reseeding(
        project, grant, tmp_path, monkeypatch):
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "working-pool-project-resume")
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path / "checkpoints"),
        save_every=2, save_on_finish=False, strict=True)
    source, outside = build(project, grant)
    original_calls = record_evaluations(source, monkeypatch)
    source.add_plugin(CheckpointResumePlugin(config=config))
    run_case(source)
    assert_committed_workspace(source, outside)
    checkpoint, = tuple((tmp_path / "checkpoints").glob("*_g000001_*.pkl"))
    expected = source.solution_pool.subpool_refs(WORKSPACE)
    expected_values = source.read_solutions(expected).numeric_matrix.copy()
    committed_prefix = expected[:70]  # 30 initial + 40 admitted before checkpoint.
    report = json.loads((project / "results" / "ga_partition.json").read_text(encoding="utf-8"))

    restored, restored_outside = build(project, grant)
    calls = record_evaluations(restored, monkeypatch)
    reader = CheckpointResumePlugin(config=config)
    restored.add_plugin(reader)
    assert reader.resume(str(checkpoint))
    run_case(restored)
    assert_committed_workspace(restored, restored_outside)
    assert restored_outside.ref == outside.ref
    actual = restored.solution_pool.subpool_refs(WORKSPACE)
    assert actual[:70] == committed_prefix
    assert len(calls) == 10  # Only the third GA update remains after checkpoint.
    np.testing.assert_array_equal(calls, original_calls[40:])
    # New proposals after a checkpoint fork can derive fresh UUIDs. Verify the
    # retained prefix by identity, and the subsequent search by evaluated values.
    np.testing.assert_array_equal(restored.read_solutions(actual).numeric_matrix, expected_values)
    np.testing.assert_array_equal(leaf(source).population, leaf(restored).population)
    np.testing.assert_array_equal(leaf(source).objectives, leaf(restored).objectives)
    trace = next(item for item in restored.plugin_manager.list_plugins() if item.name == "workflow_trace")
    assert trace.initial == report["initial"]
    assert trace.records[:2] == report["records"][:2]
    assert trace.partitions[:2] == report["partitions"][:2]
