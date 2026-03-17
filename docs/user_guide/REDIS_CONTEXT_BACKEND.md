# Redis Context Backend

This guide explains how to run NSGABlack context with a Redis backend.

## 1) What changes, what does not

- **Unchanged**: context contract, context keys, component APIs (`dict` context).
- **Changed**: where context data is synchronized (in-memory vs Redis).

Architecture:

- Component <-> local context dict <-> `ContextStore` backend

## 2) Mode A: Single shared Redis (recommended)

Use one Redis container for multiple projects, isolate by `key_prefix`.

Start once:

```powershell
docker run --name nsgablack-redis -p 6379:6379 -d --restart unless-stopped redis:7
```

Project config:

```python
solver = EvolutionSolver(
    problem,
    context_store_backend="redis",
    context_store_redis_url="redis://127.0.0.1:6379/0",
    context_store_key_prefix="nsgablack:projA",
    context_store_ttl_seconds=3600,
)
```

## 3) Mode B: One Redis per project (isolation mode)

Project A:

```powershell
docker run --name redis-projA -p 6381:6379 -d --restart unless-stopped redis:7
```

```python
context_store_redis_url="redis://127.0.0.1:6381/0"
context_store_key_prefix="nsgablack:projA"
```

Project B:

```powershell
docker run --name redis-projB -p 6382:6379 -d --restart unless-stopped redis:7
```

```python
context_store_redis_url="redis://127.0.0.1:6382/0"
context_store_key_prefix="nsgablack:projB"
```

## 4) Comparison

- **Single shared Redis**
  - Pros: lowest ops cost, simplest setup.
  - Cons: must enforce unique `key_prefix`, shared resource contention.
- **One Redis per project**
  - Pros: strongest isolation, easier incident boundary.
  - Cons: more containers/ports, higher maintenance.

## 5) Common mistakes

- `Connection refused`:
  - Redis is not running. Run `docker ps` and `docker start <name>`.
- Cross-project contamination:
  - Same `key_prefix` used in multiple projects.
- Unexpected key loss:
  - TTL expired (`context_store_ttl_seconds` too small).
- Data gone after cleanup:
  - `docker rm` or `docker compose down -v` removed container/volume.
- Misunderstanding stop/delete:
  - `docker stop` does **not** delete container data; `docker rm` does.

## 6) Standard workflow

Daily start:

```powershell
docker start nsgablack-redis
```

Health check:

```powershell
python -c "import redis; r=redis.Redis(host='127.0.0.1', port=6379, db=0); print('ping=', r.ping())"
```

Run solver with Redis backend.

Optional end-of-day stop:

```powershell
docker stop nsgablack-redis
```

## 7) Minimal framework verification

```powershell
python -c "from nsgablack.core.state.context_store import create_context_store; s=create_context_store(backend='redis', redis_url='redis://127.0.0.1:6379/0', key_prefix='nsgablack:ctxdemo', ttl_seconds=30); s.set('k', {'v':1}); print('get=', s.get('k')); print('keys=', list(s.snapshot().keys())[:5])"
```

If this prints values, Redis context backend is working.

## 8) `doctor --strict` Redis gates

With `--build --strict`, Redis config is now gated to prevent silent pollution:

- `redis-key-prefix-missing` (error): `context_store_key_prefix` is empty.
- `redis-key-prefix-too-short` (error): prefix is too short for safe namespace isolation.
- `redis-key-prefix-missing-project-name` (error): prefix does not include project token.
- `redis-ttl-invalid` (error): TTL is not numeric.
- `redis-ttl-policy-implicit` (warn): TTL policy is not explicit (`None`).
- `redis-ttl-too-small` (warn): TTL is likely too small for run lifecycle.

Example:

```powershell
python -m nsgablack project doctor --path . --build --strict
```

## 9) Run snapshot audit fields

Run Inspector snapshots now include a `context_store` block:

- `backend`
- `ttl_seconds`
- `key_prefix`
- `redis_url` (masked credential)

This makes TTL/key-prefix decisions auditable when diagnosing "keys disappeared" cases.
