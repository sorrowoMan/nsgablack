# Redis Context And Snapshot Stores

This guide explains how to use Redis for both `ContextStore` and `SnapshotStore`, and why they remain separate surfaces.

## Core Rule

- `ContextStore` carries small contract fields, control signals, and refs.
- `SnapshotStore` carries large optimization payloads such as population, objectives, violations, Pareto state, and history.
- Using Redis for both does not make them the same store semantically.

## Write Path

1. Solver, Adapter, or Plugin writes a large payload to `SnapshotStore`.
2. The store returns a `snapshot_key`.
3. The Case writes only `snapshot_key`, `population_ref`, or a small summary into context.
4. Consumers resolve the payload through `solver.read_snapshot()` or plugin helper APIs.

## Read Path

1. Read the lightweight ref from context.
2. Resolve the payload from `SnapshotStore`.
3. If the ref exists but payload is missing, treat it as a backend, TTL, or write-path failure.

## Prefix Policy

Use separate prefixes:

```text
nsgablack:ctx:<project>
nsgablack:snap:<project>
```

Use separate TTL policies:

- Context TTL protects control-plane freshness.
- Snapshot TTL protects replay and inspection windows.

## Minimal Config

```python
solver = EvolutionSolver(
    problem,
    context_store_backend="redis",
    context_store_redis_url="redis://127.0.0.1:6379/0",
    context_store_key_prefix="nsgablack:ctx:demo",
    context_store_ttl_seconds=3600,
    snapshot_store_backend="redis",
    snapshot_store_redis_url="redis://127.0.0.1:6379/0",
    snapshot_store_key_prefix="nsgablack:snap:demo",
    snapshot_store_ttl_seconds=21600,
)
```

## Troubleshooting

- Missing context fields: check context contracts and writer hooks.
- Existing ref but missing payload: check Redis connectivity, TTL, and snapshot write success.
- Stale payload: ensure consumers do not read old mirror fields directly.
- Oversized context: move payload into Snapshot or Artifact and keep only refs.
