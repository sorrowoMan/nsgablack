# plugins/system

## Purpose
System guard plugins: async events, boundary checks, memory management.

## Trigger Timing
Depends on plugin: generation start/end, init, finish.

## Input
- Solver/context snapshots and system policy config.

## Output
- Guard reports, warnings, optional committed context events.

## Side Effects
May emit warnings, update context event stream, invoke GC.

## Failure Policy
Guard plugins should prefer observability over silent failure.

## Directory Contents
- `async_event_hub.py`
- `boundary_guard.py`
- `checkpoint_resume.py`
- `memory_optimize.py`

