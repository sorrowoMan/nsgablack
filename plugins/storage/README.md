# plugins/storage

## Purpose
External persistence plugins (DB/storage bridge).

## Trigger Timing
Mainly `on_solver_finish`.

## Input
- Run result/artifacts and storage connection config.

## Output
- External run records (status/metrics/paths).

## Side Effects
Network I/O and persistent writes.

## Failure Policy
Storage failures should not corrupt optimization state.

## Directory Contents
- `mysql_run_logger.py`

