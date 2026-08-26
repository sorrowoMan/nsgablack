# Redis Context 与 Snapshot Store

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
    context_store_serializer="safe",
    context_store_max_payload_bytes=262_144,
    snapshot_store_backend="redis",
    snapshot_store_redis_url="redis://127.0.0.1:6379/0",
    snapshot_store_key_prefix="nsgablack:snap:demo",
    snapshot_store_ttl_seconds=21600,
)
```

## 信任边界

- Context 与 Snapshot 的 Redis 默认序列化都必须是 `safe`。
- `safe` 使用版本化信封，不会执行 Redis 中的 pickle，也不会把未知对象静默降级成字符串。
- `pickle_signed` 的 HMAC 必须在反序列化前校验；它只适用于写权限完全受控的环境。
- `pickle_unsafe` 与 legacy pickle 开关只允许在隔离迁移进程中短时使用，Doctor strict 会拒绝其进入正常 Case。
- 本机 Redis 端口应发布为 `127.0.0.1:6379:6379`，不能使用暴露所有网卡的 `6379:6379`。

## Troubleshooting

- Missing context fields: check context contracts and writer hooks.
- Existing ref but missing payload: check Redis connectivity, TTL, and snapshot write success.
- Stale payload: ensure consumers do not read old mirror fields directly.
- Oversized context: move payload into Snapshot or Artifact and keep only refs.
- Codec error: inspect serializer、旧 pickle、payload 上限和 HMAC，不要把解码失败当成字段不存在。
