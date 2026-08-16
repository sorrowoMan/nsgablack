# Catalog And Wiring Guide

Use Catalog when you need to answer:

- where is a component?
- what kind of component is it?
- which import path loads it?
- which companions are usually mounted with it?
- is this a framework-core entry or an example/doc entry?

## Profiles

`nsgablack` uses two catalog profiles:

| Profile | Meaning |
| --- | --- |
| `framework-core` | framework components only; use for architecture audits |
| `default` | full index including docs and examples |

Architecture conclusions must use `framework-core`:

```powershell
python -m nsgablack catalog list --profile framework-core --kind adapter
python -m nsgablack catalog search nsga2 --profile framework-core --limit 20
python -m nsgablack catalog show adapter.nsga2 --profile framework-core
```

Use `default` when looking for tutorials or example entries:

```powershell
python -m nsgablack catalog list --profile default --kind example
```

## Python Usage

```python
from nsgablack.catalog import get_catalog

catalog = get_catalog(profile="framework-core")

for entry in catalog.search("vns"):
    print(entry.key, entry.kind, entry.title)

entry = catalog.get("adapter.vns")
adapter_cls = entry.load()
```

## Wiring

Wiring helpers are official assembly shortcuts for common capability bundles. They should still be called from standard Case assembly, usually `build_solver.py`.

Examples:

```python
from nsgablack.utils.wiring import attach_benchmark_harness, attach_module_report

attach_benchmark_harness(solver)
attach_module_report(solver)
```

Wiring helpers must not become private orchestration systems. Cross-Case order and resource allocation belong to Project / L0.

## Adding Entries

Add framework entries to the registry source, then verify both profiles:

```powershell
python -m nsgablack catalog list --profile framework-core --kind adapter
python -m nsgablack catalog list --profile default --kind example
```

If an entry is a formal example, it should point to `examples/cases/<project>/run_project.py` or to a nested `cases/<case>/build_solver.py` import path inside that Project, not a compatibility wrapper.
