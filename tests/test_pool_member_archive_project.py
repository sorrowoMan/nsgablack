"""The standard GA Case can archive final members through its normal L0 build."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import numpy as np
import pytest
from blackbase.project import build_case, load_case_builder, run_case
from blackbase.resources import ResourceAllocator, ResourceContext, ResourceRequest
from nsgablack.adapters import Pool


def test_standard_case_archives_history_plus_final_members_with_default_compatibility(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "examples" / "cases" / "pool_workflow_pilot"
    allocator = ResourceAllocator()
    lease = allocator.acquire(ResourceRequest(threads=1, workers=1),
                              owner_id="member_archive_project", scope="optimization")
    resource = ResourceContext.from_mapping(lease.resource_context(namespace="member_archive_project"))
    outputs, populations = {}, {}
    try:
        for mode in ("members", "default", "invalid"):
            root = tmp_path / mode / "project"
            shutil.copytree(source, root,
                ignore=shutil.ignore_patterns("results", "__pycache__", ".blackbase", "*.pyc"))
            config = root / "cases" / "ga_search" / "config.py"
            text = config.read_text(encoding="utf-8-sig")
            for before, after in (("source_count: int = 8", "source_count: int = 6"),
                                  ("max_steps: int = 10", "max_steps: int = 3")):
                assert before in text
                text = text.replace(before, after, 1)
            if mode != "default":
                assert 'archive_source: str = "accepted"' in text
                text = text.replace('archive_source: str = "accepted"',
                                    f'archive_source: str = "{mode}"', 1)
            config.write_text(text, encoding="utf-8")
            # These modules intentionally live at Project scope. An earlier
            # copied Project must never choose this run's report destination.
            for module in ("workflow_trace", "pool_source"):
                monkeypatch.delitem(sys.modules, module, raising=False)
            builder = load_case_builder(root, "ga_search")
            if mode == "invalid":
                with pytest.raises(ValueError, match="archive_source.*accepted.*members"):
                    build_case(builder, resource_context=resource)
                assert not (root / "results").exists()
                continue
            solver = build_case(builder, resource_context=resource)
            assert solver.resource_binding_audit["current"] is True
            assert solver.resource_context.lease["lease_id"] == lease.lease_id
            leaf = solver.adapter.units[0].adapter.inner
            operation = leaf.get_bound_operator("pool_maintenance")
            assert operation.function.__name__ == (
                "maintain_final_members" if mode == "members" else "maintain_elite")
            seen, calls = [], []
            ordinary, evaluate = operation.maintain, solver.problem.evaluate

            def observe(request, *, rng):
                old = request.pool.subpool("elite")
                candidates = request.members if mode == "members" else request.accepted
                assert candidates is not None
                # With three small steps the 20-member archive never needs
                # truncation; only explicit raw ranking establishes its order.
                combined = old.merge(candidates)
                raw_f, raw_v = combined.raw_feedback()
                scores = np.column_stack((raw_v > 0., np.maximum(raw_v, 0.), raw_f.sum(axis=1)))
                order = sorted(range(len(combined)), key=lambda i: tuple(scores[i]))[:20]
                expected = combined.take(order).refs
                result = ordinary(request, rng=rng)
                if mode == "members":
                    assert result is None
                    # The ordinary function now uses the public draft syntax;
                    # inspect its local result before the real commit below.
                    assert Pool(parent=request.pool, name="elite").all().refs == expected
                else:
                    assert len(result) == 1 and result[0].name == "elite"
                    assert result[0].members == expected
                assert request.members.refs == leaf.get_population_solution_refs(solver)
                seen.append(dict(expected=expected, members=request.members.refs,
                                 accepted=request.accepted.refs))
                return result

            def record_evaluation(candidate):
                calls.append(np.array(candidate, copy=True))
                return evaluate(candidate)

            monkeypatch.setattr(operation, "maintain", observe)
            monkeypatch.setattr(solver.problem, "evaluate", record_evaluation)
            run_case(solver)
            assert solver.run_progress_steps == 3
            assert solver.evaluation_count == len(calls) == 14
            assert solver.evaluation_budget_reserved == 0
            assert len(solver.solution_pool.select(stage="initial")) == 6
            assert len(solver.solution_pool.select(stage="accepted")) == 14
            assert solver.resource_binding_audit["current"] is True
            assert len(seen) == 3
            trace = json.loads((root / "results" / "ga_search.json").read_text(encoding="utf-8"))
            assert trace["schema"] == "pool_workflow_pilot.trace/v3"
            assert [record["evaluations"] for record in trace["records"]] == [6, 10, 14]
            for record, observation in zip(trace["records"], seen, strict=True):
                assert record["elite"]["refs"] == [ref.as_dict() for ref in observation["expected"]]
                assert len(observation["members"]) == 6
            assert solver.solution_pool.subpool_refs("elite") == seen[-1]["expected"]
            assert len(trace["change_output"]["refs"]) == 8
            assert Path(sys.modules["workflow_trace"].__file__).resolve() == root / "workflow_trace.py"
            outputs[mode] = np.array(calls)
            populations[mode] = np.array(leaf.population, copy=True)
        # The optional archive source changes only the member decision input;
        # the existing accepted default preserves the actual search trajectory.
        np.testing.assert_array_equal(outputs["members"], outputs["default"])
        np.testing.assert_array_equal(populations["members"], populations["default"])
    finally:
        allocator.release(lease)
