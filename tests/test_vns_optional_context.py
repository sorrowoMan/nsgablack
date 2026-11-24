"""Optional declared neighborhood inputs must not be diagnosed as unused."""
import warnings
import numpy as np

from nsgablack.adapters import VNSAdapter
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.representation import RepresentationPipeline


def test_declared_optional_neighborhood_context_avoids_false_degradation_warning():
    class Problem(BlackBoxProblem):
        def __init__(self):
            super().__init__(dimension=1, bounds=[(0., 1.)], objectives=['min'])

        def evaluate(self, x):
            return [float(x[0])]

    class Mutation:
        context_requires = ()
        context_optional = ('vns_k', 'mutation_sigma')

        def mutate(self, candidate, context):
            return np.asarray(candidate) + float(context.get('mutation_sigma', .1))

    adapter = VNSAdapter()
    solver = ComposableSolver(Problem(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(mutator=Mutation()))
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter('always')
        adapter._warn_if_pipeline_does_not_consume_context(solver)
    assert not [item for item in captured if 'Neighborhood changes may degrade' in str(item.message)]
