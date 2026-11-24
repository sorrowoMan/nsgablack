"""A copied standard Project evaluates and reports its actual accepted version."""
import json
from pathlib import Path
import shutil

import numpy as np
import pytest

from blackbase.project import build_case, load_case_builder, run_case
from nsgablack.project.project_runner import execute_project


PROJECT = Path(__file__).resolve().parents[1] / "examples/cases/catalog_fixed_candidate"


@pytest.fixture
def fixed_project(tmp_path):
    destination = tmp_path / "catalog_fixed_candidate"
    shutil.copytree(PROJECT, destination,
                    ignore=shutil.ignore_patterns("__pycache__", ".blackbase", "results"))
    return destination


def _report(output):
    lines = [line.partition("fixed-candidate-result ")[2] for line in output.splitlines()
             if line.startswith("fixed-candidate-result ")]
    assert len(lines) == 1
    return json.loads(lines[0])


def test_standard_project_reports_one_actual_evaluation(fixed_project, capsys):
    result = execute_project(fixed_project, record=False)
    assert result.status == "ok"
    report = _report(capsys.readouterr().out)
    assert report == {"steps": 1, "evaluations": 1, "accepted_refs": 1,
                      "candidates": [[0.25, 0.75]], "raw_objectives": [[0.625]],
                      "raw_violations": [0.0]}


@pytest.mark.parametrize("options, expected", [
    ({"candidate": [0.25, 1.5]}, [0.25, 1.0]),
    ({"use_pipeline_initializer": True}, None),
])
def test_repair_and_pipeline_initialization_keep_single_evaluated_version(
        fixed_project, capsys, options, expected):
    builder = load_case_builder(fixed_project, "fixed")

    def configured(*, resource_context=None, component_overrides=None):
        return builder(options, resource_context=resource_context,
                       component_overrides=component_overrides)

    solver = build_case(configured, resource_context={"threads": 1})
    assert solver.adapter.current_unit is None
    assert solver.evaluation_count == 0
    run_case(solver)
    report = _report(capsys.readouterr().out)
    refs = solver.adapter.get_solution_pool_roots(solver)
    assert len(refs) == 1
    candidate = solver.solution_pool.read(refs).numeric_matrix
    objectives, violations = solver.solution_pool.read_raw_feedback(refs)
    if expected is not None:
        np.testing.assert_allclose(candidate, [expected])
    else:
        assert candidate.shape == (1, 2)
        assert np.all((candidate >= 0) & (candidate <= 1))
    np.testing.assert_allclose(objectives[:, 0], np.sum(candidate ** 2, axis=1))
    np.testing.assert_array_equal(violations, [0.0])
    assert report["candidates"] == candidate.tolist()
    assert report["raw_objectives"] == objectives.tolist()
    assert report["steps"] == solver.run_progress_steps == 1
    assert report["evaluations"] == solver.evaluation_count == 1
    assert solver.resource_binding_audit["current"] is True
