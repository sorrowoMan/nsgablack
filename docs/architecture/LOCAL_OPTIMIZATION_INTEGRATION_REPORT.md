# Local Optimization Integration Report

This report documents the first batch of local‑optimization integrations:
DFO trust‑region, subspace trust‑region (CUATRO_PLS‑style), non‑smooth trust‑region,
and MAS (Model‑and‑Search).

---

## 1) What was integrated

### Adapters
- `TrustRegionDFOAdapter` (DFO trust‑region baseline)
- `TrustRegionSubspaceAdapter` (subspace/low‑rank trust‑region)
- `TrustRegionNonSmoothAdapter` (non‑smooth trust‑region)
- `MASAdapter` (model‑and‑search loop)

### Plugins

### Wiring Helpers (authority wiring)

### Demos
- `examples/trust_region_dfo_demo.py`
- `examples/trust_region_subspace_demo.py`
- `examples/trust_region_nonsmooth_demo.py`
- `examples/mas_demo.py`

---

## 2) How they map to framework components

| Method | Adapter | Plugin | Bias | Pipeline |
|---|---|---|---|---|
| DFO Trust‑Region | TrustRegionDFOAdapter | (optional surrogate) | optional exploration bias | repair / init |
| Subspace TR | TrustRegionSubspaceAdapter | subspace surrogate (optional) | optional exploration bias | repair / init |
| Non‑Smooth TR | TrustRegionNonSmoothAdapter | (optional stats) | optional soft penalties | repair / init |

---

## 3) Why this validates “decomposition”

1) **Local search stays inside Adapter**  
   The search loop is fully isolated and can be swapped without affecting the solver base.

2) **Model logic sits in Plugin**  

3) **Hard constraints are enforced by the pipeline**  
   All candidates pass through `RepresentationPipeline.repair`, keeping feasibility logic centralized.

---

## 4) How to run

```bash
python examples/trust_region_dfo_demo.py
python examples/trust_region_subspace_demo.py
python examples/trust_region_nonsmooth_demo.py
python examples/mas_demo.py
```

Or attach by wiring:

```python
from nsgablack.utils.wiring import attach_trust_region_dfo, attach_mas

attach_trust_region_dfo(solver)
attach_mas(solver)
```

---

## 5) Discoverability

All new entries are registered in Catalog and API index:

- `adapter.trust_region_dfo`
- `adapter.trust_region_subspace`
- `adapter.trust_region_nonsmooth`
- `adapter.mas`

Use:

```bash
python -m nsgablack catalog search trust_region
```
