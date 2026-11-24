"""A standard Case reuses committed selector elite as real next-step parents."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

from blackbase.project import build_case, load_case_builder, run_case
from blackbase.resources import ResourceAllocator, ResourceContext, ResourceRequest
from nsgablack.adapters import MixedPoolParentSelector
from nsgablack.core.state.solution_pool import SolutionRef


def test_standard_case_uses_previous_committed_elite_for_new_children(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "examples" / "cases" / "pool_workflow_pilot"
    root = tmp_path / "project"
    shutil.copytree(source, root,
        ignore=shutil.ignore_patterns("results", "__pycache__", ".blackbase", "*.pyc"))
    config = root / "cases" / "ga_partition" / "config.py"
    data = config.read_text(encoding="utf-8-sig")
    for before, after in (("source_count: int = 100", "source_count: int = 30"),
            ("population_size: int = 100", "population_size: int = 30"),
            ("offspring_size: int = 80", "offspring_size: int = 10")):
        assert before in data
        data = data.replace(before, after, 1)
    config.write_text(data, encoding="utf-8")
    allocator = ResourceAllocator()
    lease = allocator.acquire(ResourceRequest(threads=1, workers=1),
        owner_id="selection_outputs_case", scope="optimization")
    resource = ResourceContext.from_mapping(lease.resource_context(namespace="selection_outputs_case"))
    try:
        # The shared observer writes next to its own Project. A previous
        # temporary Project must not supply this intentionally local module.
        monkeypatch.delitem(sys.modules, "workflow_trace", raising=False)
        solver = build_case(load_case_builder(root, "ga_partition"), resource_context=resource)
        calls = []
        original = solver.problem.evaluate
        def evaluate(candidate):
            calls.append(1)
            return original(candidate)
        monkeypatch.setattr(solver.problem, "evaluate", evaluate)
        run_case(solver)
        assert solver.resource_binding_audit["current"] is True
        assert solver.run_progress_steps == 3
        assert solver.evaluation_count == len(calls) == 50
        assert solver.evaluation_budget_reserved == 0
        assert solver.evaluation_batch_allowance(1) == 0
        leaf = solver.adapter.units[0].adapter.inner
        assert leaf.get_bound_operator("pool_maintenance") is None
        parent_selector = leaf.get_bound_operator("parent_selector")
        assert isinstance(parent_selector, MixedPoolParentSelector)
        assert parent_selector.pool_name == "elite" and parent_selector.pool_fraction == 1.0
        trace = json.loads((root / "results" / "ga_partition.json").read_text(encoding="utf-8"))
        assert trace["partition_schema"] == "pool_workflow_pilot.partition_trace/v2"
        assert trace["initial"]["selection_outputs_before"] == {"elite": True, "reserve": False}
        rows = trace["partitions"]
        assert [(row["input_count"], len(row["applied_refs"]),
                 len(row["selection_outputs"]["reserve"]["refs"])) for row in rows] == [
                     (30, 30, 0), (40, 30, 10), (40, 30, 10)]
        for row in rows:
            outputs = row["selection_outputs"]
            assert row["elite_from_final_members"] and not row["maintenance_bound"]
            assert outputs["elite"]["refs"] == row["applied_refs"][:20]
            assert outputs["reserve"]["refs"] == row["remaining_refs"][10:]
            for output in outputs.values():
                assert output["refs"] == [row["source_refs"][i] for i in output["positions"]]
            assert row["source_unchanged"] and row["partition_added_evaluations"] == 0
            assert row["parent_read_added_evaluations"] == 0
        assert rows[0]["previous_elite_refs"] == rows[0]["offspring_sources"] == []
        seen_tokens = {ref["candidate_token"] for ref in rows[0]["source_refs"]}
        for previous, row in zip(rows, rows[1:]):
            previous_elite = previous["selection_outputs"]["elite"]["refs"]
            assert row["previous_elite_refs"] == previous_elite
            sources = row["offspring_sources"]
            assert len(sources) == 10
            children = [SolutionRef.from_dict(item["child"]) for item in sources]
            assert len(set(children)) == len({child.candidate_token for child in children}) == 10
            assert row["source_refs"][-10:] == [item["child"] for item in sources]
            for item, child in zip(sources, children, strict=True):
                assert len(item["source_refs"]) == 2
                assert item["change_input_refs"] == item["source_refs"]
                assert all(parent in previous_elite for parent in item["source_refs"])
                assert child.candidate_token not in seen_tokens
                stored = solver.solution_pool.read_provenance((child,))[0]["metadata"]
                assert stored["change_source_refs"] == item["source_refs"]
                assert stored["change_input_refs"] == item["change_input_refs"]
            seen_tokens.update(child.candidate_token for child in children)
        for name in ("elite", "reserve"):
            first, last = (row["selection_outputs"][name] for row in (rows[0], rows[-1]))
            assert first["descriptor"]["view_id"] == last["descriptor"]["view_id"]
            assert solver.solution_pool.subpool_descriptor(name) == last["descriptor"]
            assert solver.solution_pool.subpool_refs(name) == tuple(
                SolutionRef.from_dict(ref) for ref in last["refs"])
        assert set(solver.solution_pool.subpool_refs("elite")).issubset(
            leaf.get_population_solution_refs(solver))
        assert set(solver.solution_pool.subpool_refs("reserve")).isdisjoint(
            leaf.get_population_solution_refs(solver))
    finally:
        allocator.release(lease)
