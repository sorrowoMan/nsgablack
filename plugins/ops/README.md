# plugins/ops

## Purpose
Experiment operations: benchmark, module report, profiling, sensitivity.

## Trigger Timing
Mainly `on_generation_end` and `on_solver_finish`.

## Input
- Solver runtime state, run config, output directory.

## Output
- Report files, profiling stats, experiment metadata.

## Side Effects
File I/O and runtime overhead for diagnostics.

## Failure Policy
Should warn and continue unless strict mode is explicitly requested.

## Directory Contents
- `benchmark_harness.py`
- `module_report.py`
- `profiler.py`
- `sensitivity_analysis.py`

