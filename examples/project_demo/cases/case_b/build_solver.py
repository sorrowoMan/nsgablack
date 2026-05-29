"""
A dummy solver builder for Case B.
"""
from nsgablack.core import ComposableSolver
from nsgablack.adapters import RandomSearchAdapter
from nsgablack.representation import RepresentationPipeline, RealValueRepresentation
from nsgablack.problems import DTLZ2

def build_solver():
    """Builds a simple solver for demonstration."""
    print("Building solver for Case B...")
    # This solver might depend on artifacts from Case A in a real scenario
    problem = DTLZ2(n_var=12, n_obj=3)
    
    representation = RepresentationPipeline(
        init_representation=RealValueRepresentation(problem.xl, problem.xu),
        mutate_representation=None, # Not needed for random search
    )

    adapter = RandomSearchAdapter(
        n_points=50,
        representation=representation
    )

    solver = ComposableSolver(
        problem=problem,
        adapter=adapter,
    )
    return solver
