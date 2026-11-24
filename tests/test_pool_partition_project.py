"""The real standard Case applies partition positions without extra evaluation."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

from blackbase.project import build_case, load_case_builder, run_case
from blackbase.resources import ResourceAllocator, ResourceContext, ResourceRequest
from nsgablack.core.state.solution_pool import SolutionRef


def test_standard_partition_case_applies_complement_and_respects_budget(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "examples" / "cases" / "pool_workflow_pilot"
    root = tmp_path / "project"
    shutil.copytree(source, root,
        ignore=shutil.ignore_patterns("results", "__pycache__", ".blackbase", "*.pyc"))
    config = root / "cases" / "ga_partition" / "config.py"
    data = config.read_text(encoding="utf-8-sig")
    for before, after in (("source_count: int = 100", "source_count: int = 30"),
            ("population_size: int = 100", "population_size: int = 30"),
            ("max_steps: int = 3", "max_steps: int = 2"),
            ("offspring_size: int = 80", "offspring_size: int = 10")):
        assert before in data
        data = data.replace(before, after, 1)
    config.write_text(data, encoding="utf-8")
    allocator = ResourceAllocator()
    lease = allocator.acquire(ResourceRequest(threads=1, workers=1),
        owner_id="partition_case", scope="optimization")
    resource = ResourceContext.from_mapping(lease.resource_context(namespace="partition_case"))
    try:
        solver = build_case(load_case_builder(root, "ga_partition"), resource_context=resource)
        calls = []
        original = solver.problem.evaluate
        def evaluate(candidate):
            calls.append(1)
            return original(candidate)
        monkeypatch.setattr(solver.problem, "evaluate", evaluate)
        assert run_case(solver) is not None
        assert solver.resource_binding_audit["current"] is True
        assert solver.run_progress_steps == 2
        assert solver.evaluation_count == len(calls) == 40
        assert solver.evaluation_budget_reserved == 0
        assert solver.evaluation_batch_allowance(1) == 0
        rows = json.loads((root / "results" / "ga_partition.json").read_text(encoding="utf-8"))["partitions"]
        assert [(row["input_count"], row["selected_count"], row["remaining_count"])
                for row in rows] == [(30, 20, 10), (40, 20, 20)]
        for row in rows:
            selected, remaining = row["selected_positions"], row["remaining_positions"]
            assert len(set(selected)) == 20
            assert remaining == [i for i in range(row["input_count"]) if i not in selected]
            assert row["selected_refs"] == [row["source_refs"][i] for i in selected]
            assert row["remaining_refs"] == [row["source_refs"][i] for i in remaining]
            assert row["applied_refs"] == row["selected_refs"] + row["remaining_refs"][:10]
            assert row["source_unchanged"] is True
            assert row["partition_added_evaluations"] == 0
            refs = tuple(SolutionRef.from_dict(ref) for ref in row["source_refs"])
            f, v = solver.solution_pool.read_raw_feedback(refs)
            expected = sorted(range(len(refs)), key=lambda i:
                (v[i] > 0., max(v[i], 0.), sum(f[i])))[:20]
            assert selected == expected
    finally:
        allocator.release(lease)
