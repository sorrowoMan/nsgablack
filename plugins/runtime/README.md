# plugins/runtime

## Purpose
Runtime behavior plugins: archive, dynamic switch, diversity init, plus the temporary elite-retention compatibility bridge.

## Trigger Timing
Depends on declared behavior: initialization/observation hooks, attempt hooks for legacy dynamic switching, and committed-generation hooks for Pareto archive publication.

## Input
- Current generation population/objectives/violations and solver controls.

## Output
- Runtime state updates and result summary fields.

## Side Effects
Plugins do not acquire population ownership from their lifecycle hook. Search changes belong to the owning Adapter or an explicit controller command. Elite retention is an Adapter compatibility bridge; dynamic switching and search-consuming archives still require the boundary migration described in `docs/architecture/PLUGIN_BIAS_UNIT_AUDIT_CN.md`.

## Failure Policy
Optional observers may report a declared soft error. Evaluation, preference dependencies, authoritative snapshots and strict publication failures must propagate; they cannot be converted into successful search steps.

## Directory Contents
- `diversity_init.py`
- `dynamic_switch.py`
- `elite_retention.py` — deprecated import bridge to `nsgablack.adapters.EliteRetentionAdapter`; remove_in=1.0.0.
- `pareto_archive.py`

