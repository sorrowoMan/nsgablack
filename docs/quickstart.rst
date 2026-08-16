Quickstart
==========

The current recommended workflow is the standard Project / Case / Scaffold /
L0 substrate.

Read first
----------

- ``docs/standard_scaffold_tutorial/README.md``
- ``docs/standard_scaffold_tutorial/01_create_and_run.md``

Install
-------

From source::

   git clone https://github.com/sorrowoMan/nsgablack.git
   cd nsgablack
   pip install -e .

Create a standard project
-------------------------

::

   python -m nsgablack project new my_project
   cd my_project
   python -m nsgablack project add-case my_case --type solver
   python -m nsgablack project doctor --path . --build --strict
   python run_project.py

Discover components
-------------------

::

   python -m nsgablack catalog search vns --profile framework-core
   python -m nsgablack catalog search plugin --profile framework-core
   python -m nsgablack catalog show adapter.moead --profile framework-core
