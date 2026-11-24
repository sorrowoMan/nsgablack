"""The teaching Case uses real adapters, projections, evaluations and final delivery."""
import json
from pathlib import Path
import shutil

import numpy as np
import pytest

from examples.cases.assembly_workbench.cases.directions.build_solver import build_solver
from examples.cases.assembly_workbench.cases.directions.config import DirectionsConfig
from nsgablack.core.state.solution_pool import SolutionRef
from nsgablack.project.project_runner import execute_project
from blackbase.resources import ArtifactPublisher


@pytest.fixture(scope="module", params=[None, 2], ids=["all-directions", "random-two"])
def direction_run(request, tmp_path_factory):
    output = tmp_path_factory.mktemp(f"directions-{request.param}")
    solver = build_solver(dict(direction_sample=request.param, output_dir=str(output)))
    solver.run()
    trace = json.loads((output / "trace.json").read_text(encoding="utf-8"))
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    return solver, trace, summary


def raw_objectives(candidates):
    x = np.asarray(candidates)[:, 0]
    return np.stack(((x - 1.) ** 2, (x + 1.) ** 2), axis=1)


def projected_score(view):
    projection = view["metadata"]["projection"]
    return np.max(np.abs(np.asarray(view["raw_objectives"])[0] - projection["reference"])
                  * projection["weights"])


def test_real_plan_finishes_with_exact_baseline_poll_and_return_accounting(direction_run):
    solver, trace, summary = direction_run
    selected = summary["settings"]["direction_sample"] or 3
    assert summary["plan_completed"]
    assert summary["logical_steps"] == solver.run_progress_steps == 3 + 4 * selected
    # MOEA/D bootstrap+native variation: 3+3; VNS: baseline+one trial;
    # Pattern: baseline+two poll trials; return: one reevaluation per final.
    assert summary["evaluations"] == solver.evaluation_count == 6 + 6 * selected
    assert [row["phase"] for row in trace["records"]] == (
        ["search"] * 2 + ["coarse"] * (selected * 2)
        + ["fine"] * (selected * 2) + ["return"])
    assert [row["evaluation_delta"] for row in trace["records"]] == (
        [3, 3] + [1, 1] * selected + [1, 2] * selected + [selected])
    assert trace["run_id"] == summary["run_id"] == solver.run_session.run_id
    assert all(task["status"] == "done" for task in summary["tasks"].values())
    assert summary["tasks"]["moead"]["count"] == selected
    assert summary["tasks"]["coarse"]["output"] is None
    assert summary["tasks"]["fine"]["output"] is None


def test_exact_creator_paths_and_frozen_projection_survive_two_different_refiners(direction_run):
    solver, trace, summary = direction_run
    selected = summary["settings"]["direction_sample"] or 3
    coarse, fine = summary["views"]["coarse"], summary["views"]["fine"]
    assert len(summary["views"]["moead"]) == 3
    assert len(coarse) == len(fine) == selected
    assert len({view["metadata"]["slot"] for view in coarse}) == selected
    owners = {tuple(rows[0]["metadata"]["created_by"])
              for rows in summary["views"].values()}
    assert len(owners) == 3
    at_dispatch = {row["role"]: row for row in trace["records"][1]["roles"]}
    sources = {row["descriptor"]["view_id"]: row for row in at_dispatch["moead"]["views"]}
    coarse_by_id = {view["metadata"]["view_id"]: view for view in coarse}
    for view in coarse:
        metadata = view["metadata"]
        source = sources[metadata["parent"]["view_id"]]
        assert metadata["parent"] == source["descriptor"]
        assert metadata["projection"] == source["projection"]
        assert metadata["projection"]["method"] == "tchebycheff"
        assert len(metadata["projection"]["weights"]) == len(metadata["projection"]["reference"]) == 2
    for view in fine:
        metadata = view["metadata"]
        parent = coarse_by_id[metadata["parent"]["view_id"]]
        assert metadata["parent"] == parent["descriptor"]
        assert metadata["projection"] == parent["metadata"]["projection"]
        assert metadata["slot"] == parent["metadata"]["slot"]
        direction_identity = {key: value for key, value in parent["metadata"]["parent"].items()
                              if key != "ancestors"}
        assert metadata["parent"]["ancestors"] == [direction_identity]
        assert projected_score(view) <= projected_score(parent) + 1e-12
    assert any(row["adapter_type"] == "PatternSearchAdapter"
               for row in trace["records"][-1]["roles"])
    # All views reuse existing canonical records rather than storing a second
    # candidate representation alongside their projection metadata.
    for view in coarse + fine:
        refs = tuple(SolutionRef.from_dict(value) for value in view["refs"])
        np.testing.assert_array_equal(solver.solution_pool.read(refs).numeric_matrix, view["candidates"])


def test_raw_feedback_final_receipts_and_pareto_remain_multiobjective(direction_run):
    solver, trace, summary = direction_run
    for view in [*summary["views"]["coarse"], *summary["views"]["fine"],
                 summary["final_results"], summary["final_population"]]:
        np.testing.assert_allclose(view["raw_objectives"], raw_objectives(view["candidates"]))
        np.testing.assert_array_equal(view["raw_violations"], np.zeros(len(view["refs"])))
    np.testing.assert_array_equal(summary["final_population"]["adapter_objectives"],
                                  summary["final_population"]["raw_objectives"])
    for role in ("coarse", "fine"):
        views = {view["name"]: view for view in summary["views"][role]}
        receipts = summary["result_receipts"][role]
        assert len(receipts) == len(views)
        for receipt in receipts:
            view = views[receipt["descriptor"]["name"]]
            assert receipt["descriptor"] == view["descriptor"]
            assert receipt["refs"] == view["refs"]
            assert receipt["created_by"] == view["metadata"]["created_by"]
    final_refs = tuple(SolutionRef.from_dict(value) for value in summary["final_results"]["refs"])
    assert solver.adapter.get_pool_task_results(solver, "fine") == final_refs
    assert len(trace["records"][-1]["accepted_refs"]) == len(final_refs)
    assert summary["pareto"]["size"] > 0
    np.testing.assert_allclose(summary["pareto"]["raw_objectives"],
                              raw_objectives(summary["pareto"]["candidates"]))


def test_inactive_refiners_do_not_create_units_or_publish_views(direction_run):
    _, trace, _ = direction_run
    assert all(not role["unit_exists"] and not role["current_unit_exists"]
               and not role["neighborhood_unit_exists"] for role in trace["initial"]["roles"])
    for row in trace["records"]:
        inactive = ({"coarse", "fine"} if row["phase"] == "search"
                    else {"fine"} if row["phase"] == "coarse" else set())
        for role in row["roles"]:
            if role["role"] in inactive:
                assert not role["unit_exists"] and not role["current_unit_exists"]
                assert not role["neighborhood_unit_exists"] and not role["views"]


@pytest.mark.parametrize("sample", [0, 4, True, "2"])
def test_direction_selection_count_rejects_invalid_assembly(sample):
    with pytest.raises(ValueError, match="direction_sample"):
        DirectionsConfig(direction_sample=sample)


def test_parallel_refiners_share_frozen_sources_then_return_both_final_selections(tmp_path):
    solver = build_solver(dict(refinement_layout="parallel", output_dir=str(tmp_path)))
    solver.run()
    trace = json.loads((tmp_path / "trace.json").read_text(encoding="utf-8"))
    summary = trace["summary"]
    assert summary["refinement_layout"] == "parallel"
    assert summary["returned_roles"] == ["coarse", "fine"]
    assert summary["plan_completed"] and summary["logical_steps"] == 9
    assert summary["evaluations"] == solver.evaluation_count == 27
    assert [row["phase"] for row in trace["records"]] == ["search"] * 2 + ["parallel"] * 6 + ["return"]
    assert [row["evaluation_delta"] for row in trace["records"]] == [3, 3] + [2, 3] * 3 + [6]
    sources = {row["descriptor"]["view_id"]: row for role in trace["records"][1]["roles"]
               if role["role"] == "moead" for row in role["views"]}
    for role in ("coarse", "fine"):
        assert len(summary["views"][role]) == 3
        for view in summary["views"][role]:
            metadata = view["metadata"]
            source = sources[metadata["parent"]["view_id"]]
            assert metadata["parent"] == source["descriptor"]
            assert metadata["parent"]["ancestors"] == []
            assert metadata["projection"] == source["projection"]
            np.testing.assert_allclose(view["raw_objectives"], raw_objectives(view["candidates"]))
    coarse = solver.adapter.get_pool_task_results(solver, "coarse")
    fine = solver.adapter.get_pool_task_results(solver, "fine")
    returned = tuple(SolutionRef.from_dict(value) for value in summary["final_results"]["refs"])
    assert returned == coarse + fine
    assert len(set(returned)) == 6
    assert summary["tasks"]["moead"]["count"] == len(trace["records"][-1]["accepted_refs"]) == 6
    np.testing.assert_allclose(summary["final_population"]["adapter_objectives"],
                              raw_objectives(summary["final_population"]["candidates"]))


def test_formal_directions_project_publishes_the_summary_in_its_finalization_transaction(tmp_path):
    source = Path(__file__).resolve().parents[1] / "examples/cases/assembly_workbench"
    project = tmp_path / "project"
    shutil.copytree(source, project,
        ignore=shutil.ignore_patterns("results", ".blackbase", "__pycache__", "*.pyc"))
    result = execute_project(project, group="directions")
    assert result.ok, result.as_dict()
    assert len(result.case_results) == 1
    case = result.case_results[0]
    assert case.request.case_name == "directions"
    binding = result.artifact_bindings["directions.summary"]
    assert case.artifact_refs["summary"] == binding.ref
    assert case.artifact_publications["summary"] == binding.publication
    assert binding.publication.metadata["case_finalization_sealed"] is True
    reader = ArtifactPublisher.from_resource_context(case.request.resource_context,
        project_run_id=case.identity.project_run_id, case_run_id=case.identity.case_run_id)
    published = json.loads(reader.read_verified(binding).decode("utf-8"))
    observed = json.loads((project / "results/directions/summary.json").read_text(encoding="utf-8"))
    assert published == observed
    assert published["run_id"].startswith(case.identity.case_run_id + ":solver-run:")
    assert published["logical_steps"] == 15 and published["evaluations"] == 24
    assert published["resource_binding_current"] is True
