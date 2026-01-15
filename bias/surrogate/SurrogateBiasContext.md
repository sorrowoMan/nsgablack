# SurrogateBiasContext

Context object passed into surrogate control biases.

## Purpose
- Provide runtime info (generation, population, model status) so a bias can
  adjust surrogate settings safely.

## Key fields
- `generation`, `max_generations`, `progress`
- `population`
- `surrogate_manager`, `surrogate_ready`
- `n_training_samples`, `model_quality`
- `real_eval_count`, `surrogate_eval_count`
- `prefilter`, `score_bias`, `surrogate_eval`, `constraint_eval`
- `extras`: free-form payload

## Notes
- Supports `context.get("key", default)` for safe access.
