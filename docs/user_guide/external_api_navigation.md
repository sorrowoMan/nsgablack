# External API Navigation (Core + Optional)

Goal: keep public entrypoints small, stable, and scenario-driven.

Core layers (stable):

- `core/` + `representation/` + `bias/` + `utils/(plugins|wiring helpers|contracts)` + `catalog/`

Note:

- Historical/experimental directories were removed to reduce maintenance cost.
- New ideas should land as Plugin/Wiring first (capabilities layer), then move into
  Core after contracts + tests + catalog entries are in place.

## 1) Minimal public imports (recommended)

```python
from nsgablack import get_catalog  # discoverability entrypoint

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.evolution_solver import EvolutionSolver
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.core.blank_solver import SolverBase
from nsgablack.representation import RepresentationPipeline
from nsgablack.bias import BiasModule
from nsgablack.utils.parallel import ParallelEvaluator
```

## 2) Scenario -> entrypoints

Regular multi-objective:

- Solver: `EvolutionSolver`
- With: `RepresentationPipeline` (hard feasibility) + `BiasModule` (soft guidance)

Algorithm decomposition / fusion:

- Solver: `ComposableSolver`
- Strategy: `adapters/*` (Adapter.propose/update)
- Wiring: `utils/wiring/*` (authoritative combinations)

Custom workflow / non-evolutionary prototype:

- Solver base: `SolverBase`
- Orchestration: `plugins/*`

Expensive black-box evaluation (cache / surrogate / short-circuit):

- Plugin: `plugins/evaluation/surrogate_evaluation.py` (`SurrogateEvaluationPlugin`)

Multi-strategy cooperation (roles + many units + shared facts):

- Controller: `adapters/multi_strategy/adapter.py`
- Role wrapper: `adapters/role_adapters/adapter.py`
- Assembly: direct `solver.set_adapter(...)` in `build_solver.py`

Unified experiment protocol (fair comparisons):

- Plugin: `plugins/ops/benchmark_harness.py`
- Wiring: `utils/wiring/benchmark_harness.py`

## 3) Discoverability

Use Catalog instead of searching source code:

```bash
python -m nsgablack catalog search vns
python -m nsgablack catalog search plugin
python -m nsgablack catalog search 实验
python -m nsgablack catalog show adapter.multi_strategy
```
