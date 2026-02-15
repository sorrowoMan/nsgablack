# plugins/evaluation

## Purpose
Evaluation protocol and acceleration plugins (MC, multi-fidelity, surrogate).

## Trigger Timing
Usually at generation end, evaluation stage, or solver finish.

## Input
- Solver population/objectives/violations.
- Evaluation configuration and optional model components.

## Output
- Evaluation metrics and reports.
- Optional result summary fields.

## Side Effects
May trigger extra evaluations and file writes.

## Failure Policy
Should fall back to base evaluation path when enhancement fails.

## Directory Contents
- `monte_carlo_evaluation.py`
- `multi_fidelity_evaluation.py`
- `surrogate_evaluation.py`

