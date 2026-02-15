# utils

Shared utility layer across modules.

## Purpose
- Provide reusable tooling for context, parallelism, run records, visualization,
  constraints, surrogate helpers, and engineering support.

## Trigger Timing
- Not lifecycle-triggered by default.
- Called explicitly by Problem/Pipeline/Bias/Adapter/Plugin code.

## Input
- Explicit function args, context dicts, solver/runtime structures.

## Output
- Utility return values, helper objects, serialized report content.

## Side Effects
- Some utilities do file I/O, UI rendering, caches, or parallel resource usage.

## Failure Policy
- Prefer recoverable behavior and explicit diagnostics.

## Subdirectories
- `analysis/`, `constraints/`, `context/`, `dynamic/`
- `engineering/`, `parallel/`, `performance/`, `runs/`
- `runtime/`, `suites/`, `surrogate/`, `viz/`
