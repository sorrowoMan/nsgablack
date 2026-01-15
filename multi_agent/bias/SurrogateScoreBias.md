# SurrogateScoreBias

Surrogate-based scoring bias for the multi-agent Advisor. It converts surrogate
predictions into a scalar score and can be plugged into
`advisor_score_biases`.

## Constructor

```
SurrogateScoreBias(
    surrogate_manager,
    weight=1.0,
    sign=-1.0,
    mode="mean",
    objective_weights=None,
    use_uncertainty=False,
    uncertainty_weight=0.0,
    min_samples=5,
    fallback_score=0.0,
)
```

### Key arguments

- `surrogate_manager`: a `SurrogateManager` with a trained model.
- `weight`: scaling factor for the score contribution.
- `sign`: usually `-1.0` to prefer lower surrogate predictions.
- `mode`: how to reduce multi-objective predictions to a scalar.
  - `mean` (default), or weighted mean if `objective_weights` is set.
- `use_uncertainty`: add surrogate uncertainty to the score.
- `uncertainty_weight`: weight for uncertainty term.
- `min_samples`: required samples before the bias becomes active.
- `fallback_score`: used when surrogate is not ready.

## Example usage

```
bias = SurrogateScoreBias(manager, weight=0.5, sign=-1.0)
solver = MultiAgentBlackBoxSolver(
    problem,
    config={
        "advisor_score_biases": [bias],
    },
)
```

## Notes

- The bias returns a positive score for candidates predicted to be good
  (low objective values when `sign=-1`).
- It is safe to combine with other advisor biases.
