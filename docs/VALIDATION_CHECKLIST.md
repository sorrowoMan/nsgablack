# Validation Checklist (Smoke Suite)

This checklist confirms:
1) basic tools + bias module usability
2) multi-agent with bias profiles + representation pipeline
3) representation modules availability
4) algorithmic bias library availability

## Run

```bash
python examples/validation_smoke_suite.py
```

## Expected Output

- `[1/3] basic tools + bias` and `OK`
- `[2/3] multi-agent + built-in bias profiles + representation pipeline` and `OK`
- `[3/4] representation modules smoke check` and `OK`
- `[4/4] algorithmic bias smoke check` and `OK`
- `All validation checks passed.`

## Notes

- The multi-agent check uses role bias profiles already inside the solver.
- The parallel evaluator uses `thread` backend for safe local execution.
- The suite is intentionally small to validate availability, not performance.
