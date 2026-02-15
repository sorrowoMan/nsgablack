# External API Navigation (Core + Optional)

Goal: keep public entrypoints small, stable, and scenario-driven.

Core layers (stable):

- `core/` + `representation/` + `bias/` + `utils/(plugins|suites|contracts)` + `catalog/`

Note:

- Historical/experimental directories were removed to reduce maintenance cost.
- New ideas should land as Plugin/Suite first (capabilities layer), then move into
  Core after contracts + tests + catalog entries are in place.

## 1) Minimal public imports (recommended)

```python
from nsgablack import get_catalog  # discoverability entrypoint

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.core.blank_solver import BlankSolverBase
from nsgablack.representation import RepresentationPipeline
from nsgablack.bias import BiasModule
from nsgablack.utils.parallel import ParallelEvaluator
```

## 2) Scenario -> entrypoints

Regular multi-objective:

- Solver: `BlackBoxSolverNSGAII`
- With: `RepresentationPipeline` (hard feasibility) + `BiasModule` (soft guidance)

Algorithm decomposition / fusion:

- Solver: `ComposableSolver`
- Strategy: `core/adapters/*` (Adapter.propose/update)
- Wiring: `utils/suites/*` (authoritative combinations)

Custom workflow / non-evolutionary prototype:

- Solver base: `BlankSolverBase`
- Orchestration: `plugins/*`

Expensive black-box evaluation (cache / surrogate / short-circuit):

- Plugin: `plugins/evaluation/surrogate_evaluation.py` (`SurrogateEvaluationPlugin`)

Multi-strategy cooperation (roles + many units + shared facts):

- Controller: `core/adapters/multi_strategy.py`
- Role wrapper: `core/adapters/role_adapters.py`
- Suite: `utils/suites/multi_strategy.py`

Unified experiment protocol (fair comparisons):

- Plugin: `plugins/ops/benchmark_harness.py`
- Suite: `utils/suites/benchmark_harness.py`

## 3) Discoverability

Use Catalog instead of searching source code:

```bash
python -m nsgablack catalog search vns
python -m nsgablack catalog search suite
python -m nsgablack catalog search 实验
python -m nsgablack catalog show suite.multi_strategy
```
