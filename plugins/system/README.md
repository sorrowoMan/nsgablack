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

## Checkpoint Security Notes
- `checkpoint_resume.py` uses Python `pickle`; only load checkpoints from trusted sources.
- Optional HMAC signing:
  - set env var `NSGABLACK_CHECKPOINT_HMAC_KEY`
  - plugin will sign checkpoint payloads on save and verify on resume
- Unsigned checkpoints are blocked when HMAC key is present, unless explicitly enabled:
  - `unsafe_allow_unsigned=True`
- Trusted path whitelist:
  - resume only loads from `checkpoint_dir` or `trusted_roots`.

