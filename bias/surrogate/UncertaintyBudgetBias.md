# UncertaintyBudgetBias

Adjusts the real-evaluation budget based on surrogate uncertainty.

## Constructor

```
UncertaintyBudgetBias(
    target="prefilter",
    min_real_ratio=0.1,
    max_real_ratio=0.8,
    uncertainty_low=0.05,
    uncertainty_high=0.2,
    sample_size=32,
    update_interval=1,
    min_real=None,
    force_real_when_not_ready=True,
    quality_floor=None,
    name="uncertainty_budget",
)
```

## Behavior
- Higher uncertainty → more real evaluations.
- Lower uncertainty → more surrogate usage.
- Optional `quality_floor` forces more real evaluations if model quality drops.

## When to use
- You want adaptive real-eval ratio without manual tuning.
