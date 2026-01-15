# PhaseScheduleBias

Phase-based surrogate controller that switches configs as optimization progresses.

## Constructor

```
PhaseScheduleBias(
    phases,
    use_ratio=True,
    default_phase=None,
    name="phase_schedule",
)
```

## Phase format

Each phase is a dict with `start` / `end` and update keys:

```
{
  "start": 0.0,
  "end": 0.3,
  "prefilter": {"enabled": True, "ratio": 1.0},
  "surrogate_eval": {"enabled": False},
  "score_bias": {"enabled": False},
}
```

You can also put updates under `updates: { ... }`.

## When to use
- You want a clear “warmup → mixed → surrogate-heavy” progression.
