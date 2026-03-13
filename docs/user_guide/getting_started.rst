Getting Started
===============

If you only read one thing, read the repo root guide:

- ``WORKFLOW_END_TO_END.md``

Why: it shows the canonical decomposition flow:

- ``Problem`` (objectives only)
- ``RepresentationPipeline`` (init/mutate/repair for feasibility)
- ``BiasModule`` (soft preferences)
- ``Wiring + Plugin`` (authoritative wiring + unified experiment protocol)

Install
-------

Editable install from repo root::

   pip install -e .

Then verify Catalog works::

   python -m nsgablack catalog search vns

Runnable Examples
-----------------

Run a complete end-to-end demo (writes outputs into ``runs/``)::

   python examples/end_to_end_workflow_demo.py

