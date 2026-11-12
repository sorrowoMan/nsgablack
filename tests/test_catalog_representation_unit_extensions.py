"""Source-bound extensions run through copied standard Cases and real owners."""
from pathlib import Path
import json
import shutil

import numpy as np
import pytest

from blackbase.project import build_case, load_case_builder, run_case
from nsgablack.catalog.examples import _snippet
from nsgablack.catalog.usage_learning import snippet_parts
from nsgablack.units import UnitBinding, PopulationUnit


ROOT = Path(__file__).resolve().parents[1]
BOOK = "nsgablack/docs/catalog_usage/REPRESENTATION_UNIT_EXTENSIONS_CN.md"


def _codes(key):
    source = _snippet({"nsgablack": ROOT}, {"path": BOOK, "section": "extension." + key})
    assert source["complete"] is True
    return [text for kind, text, language in snippet_parts(source) if kind == "code" and language == "python"]


def _copy(tmp_path, project):
    target = tmp_path / project
    shutil.copytree(ROOT / "examples/cases" / project, target,
                    ignore=shutil.ignore_patterns("__pycache__", ".blackbase", "results"))
    return target


def _replace_ga(project, helper, function):
    path = project / "cases/hybrid_search/adapter/composition.py"
    source = path.read_text(encoding="utf-8")
    start = source.index("    ga = NSGA2Adapter(")
    end = source.index("    vns = VNSAdapter(", start)
    source = source[:start] + f"    ga = {function}(settings)\n" + source[end:] + "\n\n" + helper
    path.write_text(source, encoding="utf-8")


def _build_ga_case(project):
    builder = load_case_builder(project, "hybrid_search")
    def configured(*, resource_context=None, component_overrides=None):
        return builder({"population_size": 4, "ga_steps": 2, "local_steps": 1, "local_batch": 1},
                       resource_context=resource_context, component_overrides=component_overrides)
    return build_case(configured, resource_context={"threads": 1})


def _ga(adapter):
    if adapter.name == "ga":
        return adapter
    for child in adapter.step_transaction_children():
        result = _ga(child)
        if result is not None:
            return result
    return None


def test_coordinate_gaussian_has_real_case_state_and_does_not_mutate_its_input(tmp_path):
    project = _copy(tmp_path, "assembled_ga_vns")
    operator, helper = _codes("repr.gaussian_mutation")
    (project / "cases/hybrid_search/pipeline/coordinate_mutation.py").write_text(operator, encoding="utf-8")
    _replace_ga(project, helper, "build_coordinate_ga")
    solver = _build_ga_case(project)
    ga = _ga(solver.adapter)
    assert ga.algorithm_unit is None
    run_case(solver)
    assert solver.run_progress_steps > 0 and solver.evaluation_count > 0
    mutator = ga.get_bound_mutator()
    parent = np.array([0.5, 0.9])
    state = mutator.get_state()
    first = mutator.mutate(parent)
    mutator.set_state(state)
    second = mutator.mutate(parent)
    np.testing.assert_array_equal(parent, [0.5, 0.9])
    np.testing.assert_array_equal(first, second)
    assert first[1] == 0.9 and not np.shares_memory(first, parent)
    assert ga.algorithm_unit.population.shape == (4, 2)


def test_simplex_pipeline_and_problem_agree_on_the_actual_evaluated_version(tmp_path, capsys):
    project = _copy(tmp_path, "catalog_fixed_candidate")
    problem, pipeline = _codes("repr.pipeline")
    (project / "cases/fixed/problem/__init__.py").write_text(problem, encoding="utf-8")
    (project / "cases/fixed/pipeline/main.py").write_text(pipeline, encoding="utf-8")
    factory = project / "cases/fixed/build_solver.py"
    source = factory.read_text(encoding="utf-8")
    assert 'options.get("candidate", (0.25, 0.75))' in source
    factory.write_text(source.replace('options.get("candidate", (0.25, 0.75))',
                                     'options.get("candidate", (0.4, 1.2))'), encoding="utf-8")
    solver = build_case(load_case_builder(project, "fixed"), resource_context={"threads": 1})
    run_case(solver)
    lines = [line.partition("fixed-candidate-result ")[2] for line in capsys.readouterr().out.splitlines()
             if line.startswith("fixed-candidate-result ")]
    assert len(lines) == 1
    report = json.loads(lines[0])
    np.testing.assert_allclose(report["candidates"], [[0.1, 0.9]])
    np.testing.assert_allclose(report["raw_objectives"], [[0.82]])
    assert report["raw_violations"] == [0.0]
    assert report["steps"] == report["evaluations"] == report["accepted_refs"] == 1
    assert solver.resource_binding_audit["current"] is True


def test_binding_compatibility_check_never_builds_a_unit(tmp_path, monkeypatch):
    project = _copy(tmp_path, "assembled_ga_vns")
    helper, = _codes("tool.unit_binding")
    _replace_ga(project, helper, "build_checked_ga")
    def forbidden(*args, **kwargs):
        raise AssertionError("Assembly compatibility inspection must not build a Unit")
    monkeypatch.setattr(UnitBinding, "build", forbidden)
    solver = _build_ga_case(project)
    ga = _ga(solver.adapter)
    assert ga.algorithm_unit is None
    description = ga.unit_binding.describe_requirement(PopulationUnit.schema, operations=("initialize",))
    assert description["match"] == "declared-compatible"
    assert ga.unit_binding.describe()["binding"] == "ga_age_structure"
    from nsgablack.representation import TrajectoryUnitBuilder
    with pytest.raises(ValueError):
        UnitBinding(TrajectoryUnitBuilder()).require(PopulationUnit.schema, operations=("initialize",))


def test_added_member_history_survives_selection_feedback_refresh_and_codec(tmp_path, monkeypatch):
    project = _copy(tmp_path, "assembled_ga_vns")
    definitions, = _codes("tool.population_unit")
    population = project / "cases/hybrid_search/pipeline/population.py"
    population.write_text(population.read_text(encoding="utf-8") + "\n\n" + definitions, encoding="utf-8")
    composition = project / "cases/hybrid_search/adapter/composition.py"
    source = composition.read_text(encoding="utf-8")
    source = source.replace("import AgePopulationBuilder", "import EnrollmentPopulationBuilder")
    source = source.replace("UnitBinding(AgePopulationBuilder())", "UnitBinding(EnrollmentPopulationBuilder())")
    composition.write_text(source, encoding="utf-8")
    solver = _build_ga_case(project)
    ga = _ga(solver.adapter)
    assert ga.algorithm_unit is None
    run_case(solver)
    unit = ga.algorithm_unit
    assert unit.entry_score.shape == unit.entry_score_known.shape == (len(unit.population),)
    assert unit.member_age.shape == unit.entry_score.shape
    saved = ga.unit_binding.dump(unit)
    def forbidden(*args, **kwargs):
        raise AssertionError("Codec recovery must not rebuild a Unit")
    monkeypatch.setattr(type(ga.unit_binding.builder), "build", forbidden)
    restored = ga.unit_binding.restore(saved)
    np.testing.assert_array_equal(restored.entry_score, unit.entry_score)
    np.testing.assert_array_equal(restored.entry_score_known, unit.entry_score_known)
    assert restored.unit_id == unit.unit_id and restored is not unit
    assert not np.shares_memory(restored.entry_score, unit.entry_score)
    # These are explicit structural contract fixtures, not Problem evaluations.
    probe = type(unit)("member-history-fixture")
    probe.initialize_population([[1.], [2.]], [[5.], [6.]], [0., 0.], candidate_tokens=("a", "b"))
    probe.apply_selection([1, 2], [[3.]], [[4.]], [0.], candidate_tokens=("c",))
    np.testing.assert_array_equal(probe.entry_score, [6., 4.])
    np.testing.assert_array_equal(probe.member_age, [1, 0])
    probe.attach_feedback([[60.], [40.]], [0., 0.])
    np.testing.assert_array_equal(probe.entry_score, [6., 4.])
    unknown = type(unit)("unevaluated-history-fixture")
    unknown.initialize_population([[1.]], candidate_tokens=("unknown",))
    np.testing.assert_array_equal(unknown.entry_score_known, [False])
