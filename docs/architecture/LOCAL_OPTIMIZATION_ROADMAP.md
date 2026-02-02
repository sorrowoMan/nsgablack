# Local Optimization Integration Roadmap

This document defines how the four local-optimization families map to NSGABlack
components (Adapter / Bias / Plugin / Pipeline). It is the implementation
contract for the upcoming integrations.

---

## A) DFO Trust-Region + Surrogate (baseline)

**Adapter**
- Trust-region local search loop
- Proposal generation inside current trust radius
- Radius update based on acceptance ratio

**Plugins**
- Surrogate model training/prediction (can reuse `SurrogateEvaluationPlugin` or a new light surrogate plugin)
- Optional uncertainty metrics for exploration bias

**Bias**
- Exploration/Exploitation bias (e.g., uncertainty-driven)

**Pipeline**
- Hard constraints in `repair` (always enforced)

---

## B) CUATRO_PLS (Subspace/Low‑Rank Trust-Region)

**Adapter**
- Subspace trust-region loop (same base as A)
- Subspace selection / update

**Plugins**
- Subspace model / low‑rank surrogate

**Bias**
- Subspace exploration bias (optional)

---

## C) Non‑Smooth / Complex‑Constraint Trust‑Region

**Adapter**
- Non-smooth TR acceptance criterion
- Inexact model handling

**Plugins**
- Non-smooth metrics / statistics (optional)

**Bias**
- Constraint‑aware soft penalties (if needed)

---

## D) MAS (Model‑and‑Search)

**Adapter**
- Alternating “model update” and “search step” cycles

**Plugins**
- Model building / selection
- Step acceptance statistics

**Bias**
- Search‑control bias (optional)

---

## E) Auto‑Designed Local Search (LSTM / Neuro‑evolution)

**Adapter**
- Executes a policy that selects local-search operators

**Plugins**
- Policy training / evolution loop

**Bias**
- Optional: exploration bias for policy

---

## Shared requirements

- All variants must:
  - Use `RepresentationPipeline.repair` for hard constraints.
  - Emit comparable metrics via BenchmarkHarness/ModuleReport.
  - Be switchable via Adapter without polluting solver core.

---

Next step: implement DFO Trust‑Region baseline as the first concrete adapter,
then incrementally extend to subspace + non‑smooth variants.
