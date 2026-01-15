# SurrogateUnifiedNSGAII

Unified surrogate interface for single NSGA-II runs. It lets you enable:

- Prefilter: pick a subset for true evaluation, fill the rest by surrogate.
- Score bias: adjust objectives using surrogate predictions.
- Surrogate eval: replace a fraction (or all) evaluations with surrogate.

This class wraps the normal `BlackBoxSolverNSGAII` flow but centralizes the
surrogate behavior in one place.

## Constructor

```
SurrogateUnifiedNSGAII(
    problem,
    surrogate_manager=None,
    surrogate_config=None,
    prefilter=None,
    score_bias=None,
    surrogate_eval=None,
    constraint_eval=None,
    surrogate_biases=None,
    min_training_samples=10,
    auto_update=True,
    update_interval=1,
)
```

### Key arguments

- `surrogate_manager`: a prepared `SurrogateManager` instance (optional).
- `surrogate_config`: dict passed to `SurrogateManager` if you do not pass one.
- `prefilter`: dict to control prefilter mode.
- `score_bias`: dict to control score bias mode.
- `surrogate_eval`: dict to control surrogate replacement mode.
- `constraint_eval`: dict controlling constraint handling for surrogate rows.
- `surrogate_biases`: list of surrogate control biases (phase/uncertainty).
- `min_training_samples`: minimum samples before surrogate is considered ready.
- `auto_update`, `update_interval`: control automatic surrogate retraining.

## Prefilter config

```
prefilter = {
    "enabled": True,
    "ratio": 0.3,          # fraction of candidates to evaluate with true objective
    "min_real": 5,
    "max_real": None,
    "strategy": "best",    # best | uncertainty | hybrid | random
    "objective_weights": None,
    "uncertainty_weight": 0.3,
}
```

## Score bias config

```
score_bias = {
    "enabled": True,
    "weight": 0.1,
    "sign": -1.0,          # negative favors lower surrogate predictions
    "mode": "vector",      # vector | scalar
    "apply_to": "real",    # real | surrogate | all
    "normalize": False,
    "objective_weights": None,
}
```

## Surrogate eval config

```
surrogate_eval = {
    "enabled": True,
    "ratio": 1.0,          # fraction replaced by surrogate (1.0 = all)
    "min_real": 0,
    "strategy": "random",  # best | uncertainty | hybrid | random
    "objective_weights": None,
    "uncertainty_weight": 0.0,
}
```

## Constraint handling

```
constraint_eval = {
    "evaluation": "real_only",  # real_only | always | skip
}
```

Notes:
- `real_only` sets surrogate rows to zero violation (treat as feasible).
- `always` evaluates constraints for all rows, even surrogate ones.
- `skip` forces zero violations for surrogate rows.

## Surrogate control biases

You can pass `surrogate_biases` to dynamically adjust configs at runtime.

Common options in `bias/surrogate`:
- `PhaseScheduleBias` (stage-based configs)
- `UncertaintyBudgetBias` (uncertainty-driven real-eval ratio)

## Example

```
solver = SurrogateUnifiedNSGAII(
    problem,
    surrogate_config={"model_type": "random_forest"},
    prefilter={"enabled": True, "ratio": 0.25, "strategy": "hybrid"},
    score_bias={"enabled": True, "weight": 0.05, "mode": "scalar"},
    surrogate_eval={"enabled": False},
    surrogate_biases=[],
)
result = solver.run()
```

## Behavior summary

- If the surrogate is not ready (not enough samples), it falls back to full
  true evaluation.
- Real evaluations are added to the surrogate training set.
- Score bias is applied after real evaluation, before selection.
