Quick Start Guide
================

This guide will get you up and running with nsgablack in just 5 minutes.

Installation
------------

Install nsgablack using pip:

.. code-block:: bash

   pip install nsgablack

Or install from source:

.. code-block:: bash

   git clone https://github.com/yourusername/nsgablack.git
   cd nsgablack
   pip install -e .

For development installation:

.. code-block:: bash

   pip install -e .[dev]

Basic Example
------------

Here's a complete example of solving a multi-objective optimization problem:

.. code-block:: python

   from nsgablack import ZDT1BlackBox, BlackBoxSolverNSGAII
   import matplotlib.pyplot as plt

   # 1. Create the optimization problem
   problem = ZDT1BlackBox(dimension=10)

   # 2. Configure the solver
   solver = BlackBoxSolverNSGAII(problem)
   solver.pop_size = 100          # Population size
   solver.max_generations = 200   # Number of generations
   solver.verbose = True           # Print progress

   # 3. Run optimization
   result = solver.run()

   # 4. Analyze results
   pareto_solutions = result['pareto_solutions']
   pareto_objectives = result['pareto_objectives']

   print(f"Found {len(pareto_solutions)} Pareto optimal solutions")
   print(f"Optimization completed in {result['generations']} generations")
   print(f"Total evaluations: {result['evaluations']}")
   print(f"Elapsed time: {result['elapsed_time']:.2f} seconds")

   # 5. Visualize results
   plt.figure(figsize=(10, 6))
   plt.scatter(pareto_objectives[:, 0], pareto_objectives[:, 1], alpha=0.7)
   plt.xlabel('Objective 1')
   plt.ylabel('Objective 2')
   plt.title('Pareto Front')
   plt.grid(True, alpha=0.3)
   plt.show()

Using the Bias System
----------------------

The bias system allows you to incorporate domain knowledge into the optimization:

.. code-block:: python

   from nsgablack import ZDT1BlackBox, BlackBoxSolverNSGAII, BiasModule

   class ConstrainedProblem(ZDT1BlackBox):
       def evaluate_constraints(self, x):
           # Constraint: sum(x) <= 5.0
           return [max(0, sum(x) - 5.0)]

   # Create constrained problem
   problem = ConstrainedProblem(dimension=10)
   solver = BlackBoxSolverNSGAII(problem)

   # Set up bias module
   bias_module = BiasModule()

   # Add constraint violation penalty
   bias_module.add_penalty_function(
       "sum_constraint",
       lambda x: max(0, sum(x) - 5.0) * 100.0  # High penalty
   )

   # Add preference for small first dimension
   bias_module.add_reward_function(
       "minimize_x0",
       lambda x: -x[0]  # Reward smaller values
   )

   # Enable bias in solver
   solver.bias_module = bias_module
   solver.enable_bias = True

   # Run optimization with bias
   result = solver.run()

Parallel Evaluation
------------------

Speed up optimization with parallel evaluation:

.. code-block:: python

   from nsgablack import ZDT1BlackBox, BlackBoxSolverNSGAII, ParallelEvaluator

   # Create expensive problem (simulated)
   class ExpensiveProblem(ZDT1BlackBox):
       def evaluate(self, x):
           import time
           time.sleep(0.01)  # Simulate expensive evaluation
           return super().evaluate(x)

   problem = ExpensiveProblem(dimension=20)
   solver = BlackBoxSolverNSGAII(problem)

   # Configure parallel evaluation
   parallel_evaluator = ParallelEvaluator(n_workers=4)
   solver.parallel_evaluator = parallel_evaluator
   solver.batch_size = 50

   # Run with parallel evaluation
   result = solver.run()

Memory Optimization
-------------------

Enable memory optimization for large problems:

.. code-block:: python

   from nsgablack import ZDT1BlackBox, BlackBoxSolverNSGAII

   # Create large problem
   problem = ZDT1BlackBox(dimension=100)
   solver = BlackBoxSolverNSGAII(problem)

   # Enable memory optimization
   solver.enable_memory_optimization = True
   solver.pop_size = 500
   solver.max_generations = 100

   # Run optimization with memory management
   result = solver.run()

Bayesian Optimization
---------------------

Use Bayesian optimization for expensive problems:

.. code-block:: python

   from nsgablack import BlackBoxProblem, BayesianOptimizer
   import numpy as np

   # Create custom problem
   class RosenbrockProblem(BlackBoxProblem):
       def __init__(self):
           super().__init__(
               name="Rosenbrock",
               dimension=5,
               bounds={f"x{i}": [-5, 5] for i in range(5)}
           )

       def evaluate(self, x):
           x = np.array(x)
           return [sum(100*(x[1:]-x[:-1]**2)**2 + (1-x[:-1])**2)]

   # Create problem and optimizer
   problem = RosenbrockProblem()
   optimizer = BayesianOptimizer(problem)

   # Configure Bayesian optimization
   optimizer.acquisition_function = 'expected_improvement'
   optimizer.kernel = 'matern_52'
   optimizer.initial_points = 20
   optimizer.max_iterations = 100

   # Run optimization
   result = optimizer.run()

   print(f"Best solution: {result['best_solution']}")
   print(f"Best objective: {result['best_objective']}")

Visualization
------------

nsgablack provides built-in visualization:

.. code-block:: python

   from nsgablack import ZDT1BlackBox, BlackBoxSolverNSGAII

   problem = ZDT1BlackBox(dimension=10)
   solver = BlackBoxSolverNSGAII(problem)
   solver.enable_visualization = True  # Enable live visualization

   # Run optimization with live plots
   result = solver.run()

   # After optimization, you can still plot results
   solver.plot_pareto_front(save_path='pareto_front.png')
   solver.plot_convergence_history(save_path='convergence.png')

Custom Problems
---------------

Define your own optimization problems:

.. code-block:: python

   from nsgablack import BlackBoxProblem
   import numpy as np

   class EngineeringProblem(BlackBoxProblem):
       def __init__(self):
           super().__init__(
               name="EngineeringDesign",
               dimension=4,
               bounds={
                   "length": [1.0, 10.0],      # meters
                   "width": [0.5, 5.0],        # meters
                   "thickness": [0.01, 0.5],   # meters
                   "material": [0, 1]         # 0=steel, 1=aluminum
               }
           )

       def evaluate(self, x):
           # Extract parameters
           length, width, thickness, material = x

           # Objective 1: Minimize mass
           density = 7850 if material == 0 else 2700  # steel or aluminum
           mass = length * width * thickness * density / 1e6

           # Objective 2: Maximize strength
           moment_of_inertia = width * thickness**3 / 12
           strength = moment_of_inertia / thickness

           return [mass, -strength]  # Minimize mass, maximize strength

       def evaluate_constraints(self, x):
           length, width, thickness, material = x
           constraints = []

           # Aspect ratio constraint
           if width > length:
               constraints.append(width - length)

           # Thickness constraint
           min_thickness = max(length, width) / 100
           if thickness < min_thickness:
               constraints.append(min_thickness - thickness)

           return constraints

   # Use the custom problem
   problem = EngineeringProblem()
   solver = BlackBoxSolverNSGAII(problem)
   result = solver.run()

Advanced Configuration
---------------------

Fine-tune solver parameters:

.. code-block:: python

   from nsgablack import ZDT1BlackBox, BlackBoxSolverNSGAII

   problem = ZDT1BlackBox(dimension=20)
   solver = BlackBoxSolverNSGAII(problem)

   # Advanced configuration
   solver.pop_size = 200
   solver.max_generations = 500
   solver.crossover_rate = 0.95
   solver.mutation_rate = 0.05
   solver.random_seed = 42  # Reproducible results

   # Enable advanced features
   solver.enable_elite_retention = True
   solver.enable_diversity_preservation = True
   solver.enable_convergence_detection = True

   # Configure convergence criteria
   solver.convergence_tolerance = 1e-6
   solver.stagnation_generations = 50

   result = solver.run()

Next Steps
----------

- 📖 **User Guide**: Comprehensive documentation for all features
- 🔧 **API Reference**: Detailed API documentation
- 💡 **Examples**: Collection of practical examples
- 📓 **Tutorials**: Step-by-step tutorials
- 🤝 **Contributing**: How to contribute to nsgablack

Need help? Check out our :doc:`user_guide/index` or ask questions on GitHub Discussions.