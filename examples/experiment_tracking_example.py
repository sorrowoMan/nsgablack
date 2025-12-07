"""Example: Experiment tracking and result management."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.base import BlackBoxProblem
from solvers.nsga2 import BlackBoxSolverNSGAII
from utils.experiment import ExperimentTracker


# Define problem
class SimpleProblem(BlackBoxProblem):
    def __init__(self):
        # BlackBoxProblem expects (name, dimension, bounds)
        super().__init__(name="Simple", dimension=2, bounds={'x0': [0, 5], 'x1': [0, 5]})
        # Provide friendly variable names for readability
        self.variables = ['x', 'y']
        # Update bounds mapping to use variable names
        self.bounds = {'x': [0, 5], 'y': [0, 5]}

    def evaluate(self, x):
        return [x[0]**2 + x[1]**2, (x[0]-5)**2 + (x[1]-5)**2]


# Run experiment
problem = SimpleProblem()
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 50
solver.max_generations = 100

# Get structured result
result = solver.run(return_experiment=True)

# Save to disk
tracker = ExperimentTracker(base_dir="./my_experiments")
exp_dir = tracker.log_run(result)
print(f"Experiment saved to: {exp_dir}")
print(f"Pareto size: {result.metrics['pareto_size']}")
print(f"Evaluations: {result.metrics['evaluation_count']}")
