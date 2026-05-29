"""
A dummy solver builder for Case A.
"""
from nsgablack.core import ComposableSolver
from nsgablack.adapters import RandomSearchAdapter
from nsgablack.representation import RepresentationPipeline, RealValueRepresentation
from nsgablack.problems import DTLZ1

def build_solver():
    """Builds a simple solver for demonstration."""
    print("Building solver for Case A...")
    problem = DTLZ1(n_var=10, n_obj=3)
    
    representation = RepresentationPipeline(
        init_representation=RealValueRepresentation(problem.xl, problem.xu),
        mutate_representation=None, # Not needed for random search
    )

    adapter = RandomSearchAdapter(
        n_points=100,
        representation=representation
    )

    solver = ComposableSolver(
        problem=problem,
        adapter=adapter,
    )
    return solver
