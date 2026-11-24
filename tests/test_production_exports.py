"""Delivered integer schedules and strict export failures are user-visible facts."""
from types import SimpleNamespace
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from examples.cases.production_scheduling.cases.production_scheduling.problem.production_problem import ProductionConstraints, ProductionSchedulingProblem
from examples.cases.production_scheduling.cases.production_scheduling.refactor_data import ProductionData
from examples.cases.production_scheduling.cases.production_scheduling.plugins.export_utils import export_schedule, choose_pareto_solutions, extract_pareto, get_export_path, write_export_summary, supply_tag_from_path
from examples.cases.production_scheduling.cases.production_scheduling.plugins.runtime_plugins import ProductionExportPlugin
from examples.cases.production_scheduling.cases.production_scheduling.pipeline.material_projection import project_schedule_material_feasible
from nsgablack.adapters import FixedCandidateAdapter
from nsgablack.core import ComposableSolver
from nsgablack.representation import RepresentationPipeline


def problem():
    data = ProductionData(2, 1, 3, np.ones((2, 1), dtype=bool), np.array([[20., 20., 20.]]), np.ones(2))
    return ProductionSchedulingProblem(data, ProductionConstraints(max_machines_per_day=2,
        min_machines_per_day=1, min_production_per_machine=2, max_production_per_machine=100,
        include_penalty_objective=False))


def test_export_creates_parent_and_preserves_exact_integer_values(tmp_path):
    path = tmp_path / 'new' / 'exports' / 'plan.csv'
    export_schedule(path, np.array([[2.9, 2.1, 0.], [0., 0., 3.8]]))
    values = pd.read_csv(path)[['Machine0', 'Machine1']].to_numpy().T
    np.testing.assert_array_equal(values, [[2, 2, 0], [0, 0, 3]])


def test_recommendations_declare_separate_tradeoffs_and_score_delivered_values():
    p = problem()
    x = np.array([[10.9, 0., 0., 0., 0., 0.], [3.9, 3.9, 3.9, 0., 0., 0.]])
    choices = choose_pareto_solutions(p, x, np.array([p.evaluate(row) for row in x]))
    assert {label for label, *_ in choices} >= {'production', 'stability', 'balanced'}
    for _, candidate, raw in choices:
        np.testing.assert_array_equal(candidate, np.floor(candidate))
        np.testing.assert_array_equal(raw, p.evaluate(candidate))


def test_export_failure_vetoes_final_result_instead_of_becoming_a_success(tmp_path):
    p = problem()
    x = np.array([2.9, 2.1, 0., 0., 0., 3.8])
    class Initializer:
        def initialize(self, problem, context):
            return x.copy()
    solver = ComposableSolver(p, adapter=FixedCandidateAdapter(),
        representation_pipeline=RepresentationPipeline(initializer=Initializer()))
    def fail_export(*args, **kwargs):
        raise OSError('export-storage-unavailable')
    plugin = ProductionExportPlugin(p, SimpleNamespace(no_export=False, export=str(tmp_path / 'plan.csv'),
        pareto_export=0, sanity_check_export=False),
        extract_pareto=lambda _: (x[None, :], np.array([p.evaluate(x)])),
        choose_pareto_solutions=choose_pareto_solutions,
        project_schedule_material_feasible=project_schedule_material_feasible,
        get_export_path=get_export_path, export_schedule=fail_export,
        write_export_summary=write_export_summary, export_pareto_batch=lambda *a, **k: 0,
        supply_tag_from_path=supply_tag_from_path)
    solver.add_plugin(plugin)
    solver.set_max_steps(1)
    with pytest.raises(Exception, match='export-storage-unavailable'):
        solver.run()
    assert not list(tmp_path.glob('*.csv'))
