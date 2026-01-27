Quickstart
==========

This project intentionally keeps the top-level namespace small.
The recommended workflow is:

- discover wiring via :code:`python -m nsgablack catalog ...`
- use :code:`ComposableSolver + Suite + Plugin` as the main path

Install
-------

From source (recommended for development)::

   git clone https://github.com/sorrowoMan/nsgablack.git
   cd nsgablack
   pip install -e .

First Run (Authoritative)
-------------------------

1) Read the end-to-end walkthrough:

- :code:`WORKFLOW_END_TO_END.md` (repo root)

2) Run a runnable demo (creates unified CSV + summary JSON outputs)::

   python examples/end_to_end_workflow_demo.py

3) Discover components::

   python -m nsgablack catalog search vns
   python -m nsgablack catalog search suite
   python -m nsgablack catalog show suite.moead

