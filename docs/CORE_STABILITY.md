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
  - `utils/plugins/` (capabilities layer)
  - `utils/suites/` (authoritative wiring)
- `catalog/`: discoverability (search/show/list)

Design principle: keep solver bases pure; bring capabilities in via
Adapter/Plugin/Bias/Representation/Suite.

## 2) Boundaries (non-goals / can change)

To reduce maintenance pressure, this repository does not ship a first-class
`experimental/` directory. Historical content is collected under
`deprecated/legacy/` and is explicitly **not** part of the stability promise.

- Historical explorations / old examples / old docs: see `deprecated/legacy/`
- New "experimental ideas": land as Plugin/Suite first; move into Core only after
  contracts + tests + catalog entries are in place
