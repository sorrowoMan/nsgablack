Getting Started
===============

If you only read one thing, read:

- ``docs/standard_scaffold_tutorial/README.md``
- ``docs/standard_scaffold_tutorial/01_create_and_run.md``

Why: the canonical entry is now Project -> Case -> Standard Scaffold, with
Project L0 granting ``ResourceContext`` to cases.

Install
-------

Editable install from repo root::

   pip install -e .

Then verify Catalog works::

   python -m nsgablack catalog search vns --profile framework-core

Create and run
--------------

::

   python -m nsgablack project new my_project
   cd my_project
   python -m nsgablack project add-case my_case --type solver
   python -m nsgablack project doctor --path . --build --strict
   python run_project.py
