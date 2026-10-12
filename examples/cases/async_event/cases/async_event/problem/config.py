"""Case-local bindings to shared framework implementation."""
from .example_problem import SphereProblem
from nsgablack.project.case_support.problem_config import create_bindings

_bindings = create_bindings(SphereProblem=SphereProblem)
ProblemConfig = _bindings.ProblemConfig
ProblemSpec = _bindings.ProblemSpec
ProblemRegistry = _bindings.ProblemRegistry
get_problem_registry = _bindings.get_problem_registry
ProblemBuilder = _bindings.ProblemBuilder
register_problem_builder = _bindings.register_problem_builder
build_problem = _bindings.build_problem
