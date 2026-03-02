# CORE_STABILITY - Core Stability And Boundaries

This document states what the project treats as "core promises" (stable) and
what is explicitly *not* a promise (can change).

## 1) Core (stable)

When building new algorithms / doing integrations, prefer relying on:

- `core/`: problem interface, solver bases, `ComposableSolver`, adapters
- `representation/`: representation pipeline and operators (init/mutate/repair/codec)
- `bias/`: bias system (domain + algorithmic + signal-driven)
- `utils/`:
  - `utils/extension_contracts.py` (executable safeguards)
  - `utils/context/context_keys.py` (canonical context keys)
  - `plugins/` (capabilities layer)
  - `utils/suites/` (authoritative wiring)
- `catalog/`: discoverability (search/show/list)

Design principle: keep solver bases pure; bring capabilities in via
Adapter/Plugin/Bias/Representation/Suite.

Why this matters: the decomposition makes extensions feel natural. New features
land in the right layer instead of the solver loop, keeping components reusable,
combinations low-friction, and regressions easier to control.

### Core conventions (must follow)

- **State Governance**: read via `solver.read_snapshot()` / `resolve_population_snapshot()`,
  write via `commit_population_snapshot()`. Never assign `solver.population` directly.
- **Instance-level RNG**: all randomness via `self._rng = np.random.default_rng()`.
  Never use `np.random.*` global functions.
- **Bias unified apply**: `_true_evaluate()` must NOT apply bias. Bias is
  applied exactly once per candidate — either by the solver's native path or
  by the plugin's own Step 5 when it takes over `evaluate_population`.
- **get_state / set_state symmetry**: if a component has `get_state()`, it must
  also implement `set_state()` for checkpoint resume.
- **Doctor `--strict`**: enforces `solver-mirror-write` and
  `plugin-direct-solver-state-access` rules via AST analysis.

See `docs/development/DEVELOPER_CONVENTIONS.md` for full details.

## 2) Boundaries (non-goals / can change)

To reduce maintenance pressure, this repository does not ship a first-class
`experimental/` directory. Historical content was previously collected under
`deprecated/legacy/` (now removed from the repo; see git history if needed)
and is explicitly **not** part of the stability promise.

- Historical explorations / old examples / old docs: see git history (the `deprecated/legacy/` directory has been cleaned)
- New "experimental ideas": land as Plugin/Suite first; move into Core only after
  contracts + tests + catalog entries are in place
