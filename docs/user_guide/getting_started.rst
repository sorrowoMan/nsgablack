Getting Started
===============

This guide will help you get started with nsgablack quickly, whether you're new to multi-objective optimization or an experienced user looking for specific features.

Installation
------------

.. note:: nsgablack requires Python 3.8 or higher.

Basic Installation
~~~~~~~~~~~~~~~~~~

Install nsgablack using pip:

.. code-block:: bash

   pip install nsgablack

Verify installation:

.. code-block:: python

   import nsgablack
   print(nsgablack.get_version())

Development Installation
~~~~~~~~~~~~~~~~~~~~~

For development with all optional dependencies:

.. code-block:: bash

   git clone https://github.com/yourusername/nsgablack.git
   cd nsgablack
   pip install -e .[dev]

Quick Verification
~~~~~~~~~~~~~~~~~

Run the quick test to verify installation:

.. code-block:: bash

   python -c "import nsgablack; print('✓ Installation successful!')"

Basic Concepts
==============

Multi-Objective Optimization
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Multi-objective optimization involves optimizing multiple conflicting objectives simultaneously. Unlike single-objective optimization where we seek one optimal solution, in multi-objective optimization we find a set of Pareto-optimal solutions representing different trade-offs.

.. important:: A solution is **Pareto-optimal** if no other solution is better in all objectives.

Pareto Front
~~~~~~~~~~~~

The set of all Pareto-optimal solutions is called the **Pareto front**. Each solution on the Pareto front represents a different trade-off between objectives.

.. image:: ../images/pareto_front.png
    :alt: Pareto front illustration
    :align: center

First Optimization
----------------

Let's solve your first multi-objective problem with nsgablack:

.. code-block:: python

   from nsgablack import ZDT1BlackBox, BlackBoxSolverNSGAII

   # 1. Define the problem
   problem = ZDT1BlackBox(dimension=10)

   # 2. Create the solver
   solver = BlackBoxSolverNSGAII(problem)

   # 3. Configure parameters
   solver.pop_size = 100          # Population size
   solver.max_generations = 200   # Number of generations
   solver.random_seed = 42         # Reproducible results

   # 4. Run optimization
   result = solver.run()

   # 5. Analyze results
   pareto_solutions = result['pareto_solutions']
   pareto_objectives = result['pareto_objectives']

   print(f"Found {len(pareto_solutions)} Pareto optimal solutions")

Understanding Results
~~~~~~~~~~~~~~~~~~~

The optimization result contains several important pieces of information:

- ``pareto_solutions``: Decision variables for Pareto-optimal solutions
- ``pareto_objectives``: Corresponding objective values
- ``generations``: Number of generations run
- ``evaluations``: Total function evaluations
- ``elapsed_time``: Time taken for optimization
- ``converged``: Whether the algorithm converged

Common Problem Types
~~~~~~~~~~~~~~~~~~~

nsgablack includes several standard test problems:

* **ZDT1**: Continuous convex Pareto front
* **ZDT3**: Disconnected Pareto front
* **DTLZ2**: Scalable to many objectives
* **Sphere**: Simple single/multi-objective test

.. code-block:: python

   # Try different problems
   from nsgablack import ZDT1BlackBox, ZDT3BlackBox, DTLZ2BlackBox, SphereBlackBox

   problems = {
       'ZDT1': ZDT1BlackBox(dimension=10),
       'ZDT3': ZDT3BlackBox(dimension=10),
       'DTLZ2': DTLZ2BlackBox(n_obj=3, n_var=12),
       'Sphere': SphereBlackBox(dimension=5)
   }

   for name, problem in problems.items():
       solver = BlackBoxSolverNSGAII(problem)
       solver.pop_size = 50
       solver.max_generations = 50
       result = solver.run()
       print(f"{name}: {len(result['pareto_solutions'])} solutions")

Configuration Options
~~~~~~~~~~~~~~~~~~~

Key solver parameters:

* ``pop_size``: Population size (default: 100)
* ``max_generations``: Maximum generations (default: 100)
* ``crossover_rate``: Crossover probability (default: 0.9)
* ``mutation_rate``: Mutation probability (default: 0.1)
* ``random_seed``: Random seed for reproducibility (optional)

.. code-block:: python

   # Fine-tune for your specific problem
   solver = BlackBoxSolverNSGAII(problem)
   solver.pop_size = 200          # Larger population for diversity
   solver.max_generations = 500  # More generations for convergence
   solver.crossover_rate = 0.95  # Higher crossover rate
   solver.mutation_rate = 0.05     # Lower mutation rate
   solver.random_seed = 123        # Reproducible results

Troubleshooting
~~~~~~~~~~~~~

Common issues and solutions:

**Import Errors**
  ::

    ImportError: No module named 'nsgablack'

  Solution: ``pip install nsgablack`` or check your Python path.

**Memory Issues**
  ::

    MemoryError: Unable to allocate array

  Solution: Reduce ``pop_size`` or enable memory optimization:

  .. code-block:: python

     solver.enable_memory_optimization = True

**Slow Convergence**
  ::

    Algorithm not converging after many generations

  Solution:
  - Increase population size
  - Adjust crossover/mutation rates
  - Enable diversity preservation
  - Check problem definition

**No Solutions Found**
  ::

    Zero Pareto solutions found

  Solution:
  - Check problem bounds
  - Verify objective function returns correct values
  - Increase population size
  - Check for numerical issues

Next Steps
~~~~~~~~~~~

Now that you understand the basics:

1. Learn about the :doc:`bias_system/index` for domain knowledge integration
2. Explore :doc:`algorithms/index` for different optimization algorithms
3. Check :doc:`examples/index` for practical applications
4. Read :doc:`user_guide/advanced_topics` for advanced techniques

Need Help?
~~~~~~~~~

* 📖 **Documentation**: Complete API reference and guides
* 🤝 **Community**: GitHub Discussions for questions
* 🐛 **Issues**: Report bugs on GitHub
* 💬 **Examples**: More detailed examples in the examples directory

Happy optimizing with nsgablack! 🚀