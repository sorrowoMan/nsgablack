# SurrogateControlBias

Base class for surrogate control biases.

## Role
- Standardize how a bias computes updates for surrogate configs.

## Methods
- `should_apply(context) -> bool`
- `apply(context) -> dict`
- `__call__(context) -> dict`

## Returned update keys (typical)
- `prefilter`
- `score_bias`
- `surrogate_eval`
- `constraint_eval`
- `min_training_samples`, `auto_update`, `update_interval`
