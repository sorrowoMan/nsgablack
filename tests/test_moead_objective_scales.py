"""Direction comparisons and exported tasks share units without changing raw F."""
import copy
import numpy as np
import pytest

from nsgablack.adapters import MOEADAdapter
from nsgablack.adapters.subpools import adapter_path
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.state.pool_views import ObjectiveProjection
from nsgablack.representation import RepresentationPipeline


class DifferentUnits(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, bounds=[(0., 10.)], objectives=['min', 'min'])

    def evaluate(self, x):
        return [-100000. * x[0], x[0] ** 2]


class Start:
    def initialize(self, problem, context):
        return np.array([2.])


@pytest.mark.parametrize('method', ['weighted_sum', 'tchebycheff'])
def test_scaled_direction_views_match_replacement_and_preserve_raw(method):
    adapter = MOEADAdapter(population_size=4, batch_size=4, decomposition=method,
                           objective_scales=(100000., 1.))
    solver = ComposableSolver(DifferentUnits(), adapter=adapter,
                              representation_pipeline=RepresentationPipeline(initializer=Start()))
    solver.setup()
    assert solver.step().committed
    pool = solver.solution_pool
    names = pool.projection_subpools(adapter_path(adapter, adapter))
    assert len(names) == 4
    np.testing.assert_array_equal(adapter.pop_F, np.tile([-200000., 4.], (4, 1)))
    original = OptimizationFeedbackBatch.from_arrays([[-190000., 3.61]], [0.])
    for name in names:
        meta = pool.subpool_metadata(name)
        slot = meta['slot']
        projection = ObjectiveProjection.from_dict(meta['projection'])
        np.testing.assert_allclose(projection.weights, adapter.weights[slot] / [100000., 1.])
        projected = projection.apply(original)
        assert projected.objectives[0, 0] == pytest.approx(adapter._g(original.objectives[0], adapter.weights[slot]))
        np.testing.assert_array_equal(projected.raw_objectives, original.objectives)
        np.testing.assert_array_equal(original.objectives, [[-190000., 3.61]])


def test_scale_can_change_which_tradeoff_is_better():
    adapter = MOEADAdapter(decomposition='weighted_sum', objective_scales=(100000., 1.))
    # A 100-piece gain cannot outweigh a whole unit of stability degradation.
    assert adapter._g([-70000., .2], [.5, .5]) < adapter._g([-70100., 1.2], [.5, .5])
    unscaled = MOEADAdapter(decomposition='weighted_sum')
    assert unscaled._g([-70000., .2], [.5, .5]) > unscaled._g([-70100., 1.2], [.5, .5])


@pytest.mark.parametrize('scales', [(), (0., 1.), (-1., 1.), (np.inf, 1.), (np.nan, 1.), [[1., 2.]]])
def test_invalid_scales_fail_at_assembly(scales):
    with pytest.raises(ValueError, match='objective scales'):
        MOEADAdapter(objective_scales=scales)


def test_scale_dimension_fails_before_problem_evaluation():
    adapter = MOEADAdapter(objective_scales=(100000.,))
    solver = ComposableSolver(DifferentUnits(), adapter=adapter,
                              representation_pipeline=RepresentationPipeline(initializer=Start()))
    with pytest.raises(ValueError, match='align'):
        solver.setup()
    assert solver.evaluation_count == 0


def test_positive_scale_cannot_overflow_the_comparison_frame():
    adapter = MOEADAdapter(objective_scales=(1e-320, 1.))
    solver = ComposableSolver(DifferentUnits(), adapter=adapter,
                              representation_pipeline=RepresentationPipeline(initializer=Start()))
    with pytest.raises(ValueError, match='non-finite comparison weights'):
        solver.setup()
    assert solver.evaluation_count == 0


def test_checkpoint_does_not_silently_change_comparison_units():
    source = MOEADAdapter(objective_scales=(100000., 1.))
    state = copy.deepcopy(source._get_algorithm_state())
    MOEADAdapter(objective_scales=(100000., 1.))._set_algorithm_state(state)
    with pytest.raises(ValueError, match='checkpoint objective scales'):
        MOEADAdapter(objective_scales=(1., 1.))._set_algorithm_state(state)
    old_state = dict(state)
    old_state.pop('objective_scales')
    with pytest.raises(ValueError, match='checkpoint objective scales'):
        source._set_algorithm_state(old_state)
    MOEADAdapter()._set_algorithm_state(old_state)
