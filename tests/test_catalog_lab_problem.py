"""A user Problem is one definition in editor, real Case and raw verifier."""
from __future__ import annotations

import ast
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import types

import numpy as np
import pytest

from nsgablack.catalog.lab_assembly import assembly_catalog, assembly_from_recipe, normalize_assembly
from nsgablack.catalog.lab_problem import (
    LabProblem, ProblemUniformInitializer, display_objectives, evaluate_problem,
    normalize_problem, objective_count, objective_definitions, problem_bounds, problem_definition_source)
from nsgablack.catalog.lab_project import export_project, preview_files


def _profit():
    return dict(component="problem.expression", parameters=dict(
        variables=[dict(name="quantity", low=0, high=10, type="continuous")],
        objectives=[dict(name="利润", expression="8*quantity-quantity**2", direction="max")],
        constraints=[dict(name="资源", expression="quantity", relation="<=", rhs=6, tolerance=.1)]))


def test_custom_problem_normalization_preserves_semantics_and_has_one_ai_contract():
    original = _profit()
    normalized = normalize_problem(original, 1)
    assert normalized == original
    normalized["parameters"]["variables"][0]["low"] = -1
    assert original["parameters"]["variables"][0]["low"] == 0
    assert problem_bounds(original) == [(0., 10.)]
    assert objective_count(original) == 1
    assert objective_definitions(original) == original["parameters"]["objectives"]
    catalog = assembly_catalog()
    row = next(r for r in catalog["components"]["problems"] if r["key"] == "problem.expression")
    assert row["definition"] == catalog["problem_definition"]
    assert normalize_problem(catalog["problem_definition"]["example"])["component"] == "problem.expression"
    assert json.loads(json.dumps(catalog)) == catalog


def test_maximization_hard_constraints_tolerance_and_bounds_are_separate():
    binding = _profit()
    assert evaluate_problem(binding, [4]) == ([-16.], 0.)
    values, violation = evaluate_problem(binding, [7])
    assert values == [-7.]
    assert violation == pytest.approx(.9)
    assert display_objectives(binding, values) == [7.]
    # Bounds have their own violation and are not silently clipped in evaluation.
    assert evaluate_problem(binding, [-2]) == ([20.], 2.)
    assert evaluate_problem(binding, [11])[1] == pytest.approx(5.9)
    problem = LabProblem(1, binding)
    assert problem.variables == ["quantity"] and problem.bounds == [(0., 10.)]
    assert problem.evaluate([7]) == [-7.]
    np.testing.assert_allclose(problem.evaluate_constraints([7]), [0., .9])
    np.testing.assert_allclose(problem.evaluate_constraints([[4], [7]]), [[0., 0.], [0., .9]])
    assert problem.evaluation_count == 1
    assert problem.is_valid([4]) is True and problem.is_valid([7]) is False


def test_constraint_relations_share_the_same_violation_algebra():
    binding = _profit()
    binding["parameters"]["constraints"] = [
        dict(name="最少", expression="quantity", relation=">=", rhs=3, tolerance=.25),
        dict(name="等量", expression="2*quantity", relation="==", rhs=8, tolerance=.5)]
    assert evaluate_problem(binding, [4])[1] == 0
    assert evaluate_problem(binding, [2])[1] == 4.25
    assert evaluate_problem(binding, [5])[1] == 1.5


@pytest.mark.parametrize("formula", [
    "__import__('os').system('echo pwned')", "quantity.real", "quantity[0]",
    "(lambda: 1)()", "[quantity for _ in range(5)]", "[1,2]", "{'x':1}",
    "sum((quantity,1))", "open('/tmp/x')", "sqrt(x=quantity)", "quantity > 1",
    "quantity if quantity else 0", "True", "'text'", "unknown+1", "min(quantity)",
    "quantity**quantity", "quantity**1000000", "quantity**2.1", "quantity**(2+2)",
    "sin()", "cos(quantity,1)", "-" * 30 + "quantity", "quantity+" * 70 + "1",
])
def test_expression_interpreter_rejects_python_or_unbounded_work(formula):
    binding = _profit()
    binding["parameters"]["objectives"][0]["expression"] = formula
    with pytest.raises(ValueError):
        normalize_problem(binding)


@pytest.mark.parametrize("change", [
    lambda p: p["parameters"]["variables"][0].update(type="integer"),
    lambda p: p["parameters"]["variables"][0].update(name="pi"),
    lambda p: p["parameters"]["variables"][0].update(name="sin"),
    lambda p: p["parameters"]["variables"][0].update(name="__dict__"),
    lambda p: p["parameters"]["variables"][0].update(low=True),
    lambda p: p["parameters"]["variables"][0].update(high=float("inf")),
    lambda p: p["parameters"]["variables"][0].update(high=0),
    lambda p: p["parameters"]["variables"].append(p["parameters"]["variables"][0]),
    lambda p: p["parameters"]["objectives"][0].pop("direction"),
    lambda p: p["parameters"]["constraints"][0].pop("relation"),
    lambda p: p["parameters"]["constraints"][0].pop("rhs"),
    lambda p: p["parameters"]["constraints"][0].update(tolerance=-1),
    lambda p: p["parameters"]["constraints"][0].update(relation="<"),
    lambda p: p["parameters"].update(evaluator="https://example.com"),
    lambda p: p.update(component="problem.external"),
])
def test_custom_problem_does_not_guess_missing_or_unsupported_semantics(change):
    binding = _profit()
    change(binding)
    with pytest.raises(ValueError):
        normalize_problem(binding)


def test_math_functions_and_runtime_domain_errors_are_explicit():
    binding = _profit()
    binding["parameters"]["objectives"][0].update(direction="min",
        expression="sqrt(quantity)+log(quantity)+exp(0)+sin(pi/2)+cos(0)+abs(-2)+min(1,2)+max(2,3)+quantity%2+quantity**-1")
    objectives, _ = evaluate_problem(binding, [1])
    assert objectives == [12.]
    binding["parameters"]["constraints"][0]["expression"] = "1/(quantity-4)"
    problem = LabProblem(1, binding)
    with pytest.raises(ValueError, match="求值失败"):
        problem.evaluate([4])
    binding["parameters"]["constraints"] = []
    binding["parameters"]["objectives"][0]["expression"] = "exp(quantity*1000)"
    with pytest.raises(ValueError, match="求值失败"):
        evaluate_problem(binding, [1])
    for candidate in ([float("nan")], [[1]], [1, 2]):
        with pytest.raises(ValueError):
            evaluate_problem(binding, candidate)


def test_vector_initializer_uses_actual_bounds_and_restores_rng():
    binding = _profit()
    binding["parameters"]["variables"].append(dict(name="price", low=100, high=105))
    initializer = ProblemUniformInitializer(binding, 2)
    problem = LabProblem(2, binding)
    initializer.set_random_seed(17)
    for _ in range(10):
        x = initializer.initialize(problem)
        assert 0 <= x[0] <= 10 and 100 <= x[1] <= 105
    state = initializer.get_state()
    expected = initializer.initialize(problem)
    initializer.set_state(state)
    np.testing.assert_array_equal(initializer.initialize(problem), expected)
    other = copy.deepcopy(binding)
    other["parameters"]["variables"][1]["high"] = 106
    with pytest.raises(ValueError, match="identity"):
        ProblemUniformInitializer(other, 2).set_state(state)


def test_one_variable_is_supported_dimension_does_not_silently_drift_and_moead_stays_multiobjective():
    normalized = normalize_assembly(dict(problem=_profit(), nodes=[dict(id="ga", component="adapter.nsga2")]))
    assert normalized["dimension"] == 1
    assert normalized["pipeline"]["initializer"] == dict(component="repr.problem_uniform", parameters={})
    assert normalize_assembly(normalized) == normalized
    with pytest.raises(ValueError, match="dimension"):
        normalize_problem(_profit(), 2)
    normalized["dimension"] = 2
    with pytest.raises(ValueError, match="dimension"):
        normalize_assembly(normalized)
    with pytest.raises(ValueError, match="1 个原始目标"):
        normalize_assembly(dict(problem=_profit(), nodes=[dict(id="m", component="adapter.moead")]))
    with pytest.raises(ValueError, match="repr.problem_uniform"):
        normalize_assembly(dict(problem=_profit(), nodes=[dict(id="ga", component="adapter.nsga2")],
            pipeline=dict(initializer=dict(component="repr.uniform", parameters=dict(low=-1, high=1)))))


def test_preview_exports_the_same_interpreter_and_does_not_evaluate_formulas(monkeypatch):
    binding = _profit()
    binding["parameters"]["objectives"][0]["expression"] = "1/0"
    spec = normalize_assembly(dict(problem=binding, nodes=[dict(id="sa", component="adapter.sa")]))
    files = preview_files(spec)
    assert files["cases/search/problem/__init__.py"] == problem_definition_source()
    for name, code in files.items():
        if name.endswith(".py"):
            ast.parse(code, filename=name)
    scope = types.ModuleType("exported_problem")
    exec(files["cases/search/problem/__init__.py"], scope.__dict__)
    def deny(*args, **kwargs):
        raise AssertionError("user expression must not use eval")
    monkeypatch.setattr("builtins.eval", deny)
    with pytest.raises(ValueError, match="求值失败"):
        scope.build_problem(spec).evaluate([1])
    # Same contract and same directions in the exported implementation.
    assert scope.normalize_problem(_profit()) == normalize_problem(_profit())
    assert scope.evaluate_problem(_profit(), [4]) == evaluate_problem(_profit(), [4])


@pytest.mark.parametrize("repair", ["repr.clip", "repr.box_projection"])
def test_exported_real_project_uses_custom_problem_in_pool_evaluation_repair_and_raw_evidence(tmp_path, repair):
    binding = _profit()
    binding["parameters"]["variables"].append(dict(name="price", low=100, high=105, type="continuous"))
    binding["parameters"]["objectives"].append(dict(name="成本", expression="price+quantity", direction="min"))
    # Every point has a positive, measurable violation, so raw evidence cannot be
    # verified merely by assuming zero or by checking the old demo bounds.
    binding["parameters"]["constraints"][0].update(expression="price", rhs=90, tolerance=.5)
    spec = normalize_assembly(dict(problem=binding, initial_count=8, max_steps=3,
        pipeline=dict(repair=dict(component=repair)),
        nodes=[dict(id="ga", component="adapter.nsga2", change="ga_mask",
                    parameters=dict(population_size=4, offspring_size=4))],
        plan=dict(kind="stage", node="ga", steps=3)))
    project = export_project(spec, tmp_path / "project")
    repo = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(repo), str(repo.parent), os.environ.get("PYTHONPATH", "")])}
    run = subprocess.run([sys.executable, "run_project.py", "--run-id", "custom-problem"], cwd=project,
        env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    assert run.returncode == 0, run.stdout[-5000:] + run.stderr[-5000:]
    report = json.loads((project / "results/lab_report.json").read_text(encoding="utf-8"))
    assert report["plan_completed"] is True
    assert report["spec"] == spec
    rows = report["result"]
    assert rows["candidates"]
    for x, objectives, violation in zip(rows["candidates"], rows["raw_objectives"], rows["raw_violations"]):
        assert 0 <= x[0] <= 10 and 100 <= x[1] <= 105
        expected_objectives, expected_violation = evaluate_problem(binding, x)
        np.testing.assert_allclose(objectives, expected_objectives)
        assert violation == pytest.approx(expected_violation) and violation > 0
        np.testing.assert_allclose(display_objectives(binding, objectives), [8*x[0]-x[0]**2, x[1]+x[0]])
