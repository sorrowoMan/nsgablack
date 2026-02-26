# Decision Replay Engine

Decision Replay focuses on **why a decision happened**, not only solver state snapshots.

## What it records

Each decision event has:

- `seq`: stable replay sequence id
- `generation`, `step`
- `event_type` (e.g. `fallback`, `inner_budget`, `surrogate_trigger`)
- `component`
- `decision`
- `reason_code`
- `inputs`, `thresholds`, `evidence`, `outcome`

Artifacts:

- `runs/<run_id>.decision_trace.jsonl`
- `runs/<run_id>.decision_trace.summary.json`

## Quick usage

```python
from nsgablack.plugins import DecisionTracePlugin, DecisionTraceConfig

solver.add_plugin(
    DecisionTracePlugin(
        config=DecisionTraceConfig(output_dir="runs", run_id="exp1")
    )
)
```

## Emit semantic decisions from any component

```python
from nsgablack.utils.runtime import record_decision_event

record_decision_event(
    solver,
    event_type="fallback",
    component="plugin.surrogate_router",
    decision="fallback_to_truth",
    reason_code="surrogate_confidence_below_threshold",
    inputs={"confidence": 0.42},
    thresholds={"min_confidence": 0.7},
    evidence={"window": 16},
    outcome={"mode": "truth_eval"},
)
```

## Replay

```python
from pathlib import Path
from nsgablack.utils.runtime import DecisionReplayEngine

engine = DecisionReplayEngine.from_jsonl(Path("runs/exp1.decision_trace.jsonl"))
print(engine.summary())
for e in engine.iter(event_type="fallback"):
    print(e["generation"], e["decision"], e["reason_code"])
```

## Demo

```powershell
python examples/decision_trace_demo.py
```
