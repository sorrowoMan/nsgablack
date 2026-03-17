# plugins/runtime

## Purpose
Runtime behavior plugins: elite retention, archive, dynamic switch, diversity init.

## Trigger Timing
Mostly `on_solver_init`, `on_population_init`, `on_generation_end`.

## Input
- Current generation population/objectives/violations and solver controls.

## Output
- Runtime state updates and result summary fields.

## Side Effects
May directly mutate solver state or population content.

## Failure Policy
Default should degrade safely; strict mode may fail fast.

## Directory Contents
- `diversity_init.py`
- `dynamic_switch.py`
- `elite_retention.py`
- `pareto_archive.py`

