# Catalog DB Protocol

## Purpose

`nsgablack` catalog now has two formal read surfaces:

- in-memory registry
- materialized SQL catalog store

This document writes down the local configuration contract so future CLI, dashboard,
tests, and agents all use the same rules.

The goal is to eliminate ambiguity around:

- where local DB config lives
- which source wins when multiple config sources exist
- how PostgreSQL / MySQL are selected
- when reads come from DB vs registry
- how to materialize and verify the persisted catalog surface

## Supported Backends

Current `nsgablack` catalog DB backends:

- PostgreSQL
- MySQL

## Formal Persisted Surface

`nsgablack` PostgreSQL catalog now exposes a formal persisted catalog surface aligned with
the newer `mlblack` style:

- `catalog_profiles`
- `catalog_entries`
- `catalog_scalars`

Meaning:

- `catalog_profiles`: one row per materialized profile
- `catalog_entries`: one row per catalog entry in that profile
- `catalog_scalars`: scalarized field values used for filter / facet / search

Important compatibility note:

- older decomposed tables such as `catalog_component`, `catalog_context_contract`,
  `catalog_usage_contract`, `catalog_param_contract`, `catalog_method_contract`,
  `catalog_health`, and `catalog_field_value` may still exist in older PostgreSQL DBs
- current PostgreSQL read path now prefers the formal persisted surface above
- legacy decomposed tables are not auto-dropped
- once you explicitly run PostgreSQL legacy cleanup, future PostgreSQL materialize
  stays on the formal surface and does not recreate those old split tables

Current accepted explicit URL schemes:

- `postgresql://...`
- `postgres://...`
- `postgresql+psycopg://...`
- `postgresql+psycopg2://...`
- `mysql://...`
- `mysql+pymysql://...`
- `mysql+mysqlconnector://...`

## Hard Local Rules

1. Real local config file is `catalog/db.toml`.
2. `catalog/db.toml` is local-only and must not be committed.
3. Version the template only: `catalog/db.toml.example`.
4. In one `catalog/db.toml`, enable only one backend block at a time.
5. If you need to bypass local config, pass an explicit URL with `--db-url` or `--db-path`.

Important current implementation detail:

- if both `[postgres]` and `[mysql]` are enabled and you do not pass an explicit URL,
  current backend resolution prefers PostgreSQL first

So the safe rule is:

- never enable both at once

## Local Files

### Versioned template

- [catalog/db.toml.example](C:/Users/hp/Desktop/nsgablack/catalog/db.toml.example)

### Real local file

- `catalog/db.toml`

### Ignore policy

`catalog/db.toml` is already gitignored in this repo.

## Config Resolution Order

Catalog DB target resolution currently follows this priority.

### 1. Explicit CLI / API target

If you pass:

- `--db-url` for materialization
- `--db-path` for dashboard / facade reads
- `db_url=...` / `db_path=...` in Python calls

that explicit URL wins.

The backend is chosen from the URL scheme itself.

### 2. Environment URL

- `NSGABLACK_CATALOG_DB_URL`

If this variable is set, backend is chosen from the URL scheme.

### 3. Custom TOML path

- `NSGABLACK_CATALOG_DB_CONFIG`

If set, loader reads that TOML file first.

### 4. Local TOML file

- `./catalog/db.toml`

If the current working directory is not the repo root, the loader also checks the package-side
`catalog/db.toml` inside the installed/checked-out project.

## Source Mode Resolution

Read mode resolution follows this order:

1. explicit `source_mode` / `--source-mode`
2. `NSGABLACK_CATALOG_DB_MODE`
3. backend block `mode` in `catalog/db.toml`
4. default `prefer`

Supported modes:

- `prefer`: 数据库只作为当前源码 Catalog 的物化缓存。读取前会比较稳定的
  `source_digest`；摘要缺失或不一致时只读回退到 registry，并通过
  `catalog_source_info()` 暴露 `db_stale` / `db_stale_reason`。
- `only`
- `off`
- `disabled` as alias for `off` in env/file mode parsing

## `catalog/db.toml` Schema

`nsgablack` currently uses backend-specific blocks, not a generic `[catalog_db]` block.

### PostgreSQL block

Use either:

- `[postgres]`
- `[postgresql]`

Fields:

```toml
[postgres]
enabled = true
mode = "prefer"
readonly = false

# Either explicit URL:
url = "postgresql://postgres:YOUR_PASSWORD@localhost:5432/nsgablack"

# Or structured fields:
host = "localhost"
port = 5432
user = "postgres"
password = "YOUR_PASSWORD"
database = "nsgablack"
connect_timeout = 10
```

### MySQL block

```toml
[mysql]
enabled = true
mode = "prefer"
readonly = false

# Either explicit URL:
url = "mysql://root:YOUR_PASSWORD@127.0.0.1:3306/nsgablack"

# Or structured fields:
host = "127.0.0.1"
port = 3306
user = "root"
password = "YOUR_PASSWORD"
database = "nsgablack"
connect_timeout = 10
```

## Environment Variables

### `NSGABLACK_CATALOG_DB_URL`

Provides the effective DB target directly.

Examples:

```powershell
$env:NSGABLACK_CATALOG_DB_URL = "postgresql://postgres:YOUR_PASSWORD@localhost:5432/nsgablack"
$env:NSGABLACK_CATALOG_DB_URL = "mysql://root:YOUR_PASSWORD@127.0.0.1:3306/nsgablack"
```

### `NSGABLACK_CATALOG_DB_MODE`

Overrides file `mode`.

Examples:

```powershell
$env:NSGABLACK_CATALOG_DB_MODE = "prefer"
$env:NSGABLACK_CATALOG_DB_MODE = "only"
$env:NSGABLACK_CATALOG_DB_MODE = "off"
```

### `NSGABLACK_CATALOG_DB_CONFIG`

Points to a custom TOML file.

Example:

```powershell
$env:NSGABLACK_CATALOG_DB_CONFIG = "C:\Users\hp\Desktop\nsgablack\catalog\db.toml"
```

### `NSGABLACK_CATALOG_DB_READONLY`

This is mainly meaningful when DB target is resolved from environment URL.

Truthy values:

- `1`
- `true`
- `yes`
- `on`

## Read Routing Semantics

Most user-facing catalog reads go through facade routing:

- `list_entries`
- `search_entries`
- `show_entry`
- `catalog_summary`
- `catalog_schema`
- `field_values`
- `catalog_neighbors`
- `catalog_facets`
- `catalog_ui_snapshot`
- `catalog_source_info`

### Mode `prefer`

Behavior:

- if DB target is configured and reachable, read from DB
- otherwise fall back to in-memory registry

Recommended for normal local browsing.

### Mode `only`

Behavior:

- DB target must be configured or explicitly provided
- DB target must be reachable

Otherwise the read errors out.

Recommended for:

- persisted catalog verification
- dashboard sessions that must not silently fall back
- CI-style strict checks

### Mode `off`

Behavior:

- always read from registry
- DB config may exist, but reads ignore it

Recommended for fast local debugging when you want to bypass SQL entirely.

### Explicit `db_path`

If dashboard/facade read calls pass explicit `db_path` / `--db-path`:

- backend comes from that URL scheme
- the call becomes effectively DB-directed
- `source_mode=only` is the clearest matching behavior

Note:

- despite the flag name `db-path`, current implementation also accepts full SQL URLs

## Materialization Semantics

CLI:

```powershell
python -m nsgablack catalog materialize --profile framework-core --db-url "postgresql://postgres:YOUR_PASSWORD@localhost:5432/nsgablack"
python -m nsgablack catalog materialize --profile framework-core --db-url "mysql://root:YOUR_PASSWORD@127.0.0.1:3306/nsgablack"
```

Python:

```python
from nsgablack.catalog import materialize_catalog_to_db

payload = materialize_catalog_to_db(
    profile="framework-core",
    db_url="postgresql://postgres:YOUR_PASSWORD@localhost:5432/nsgablack",
)
```

Write behavior:

- catalog contracts are materialized into the selected backend
- PostgreSQL 在每个 profile 的 `schema_json` 中保存源码 schema 与稳定摘要；
  `default` 和 `framework-core` 必须分别物化
- MySQL 保留默认全集并在查询时应用 profile；再次物化会删除源码中已经退役的
  component 及其 contract/health/scalar 子记录，而不是永久累积旧条目
- returned payload includes `backend`
- local `readonly` config prevents accidental writes when store is constructed in readonly mode
- explicit `--db-url` materialization is the normal intentional write path

## One-Time PostgreSQL Hard Cleanup

If your PostgreSQL catalog still contains the older split-table surface, use the dedicated
cleanup command after you have already materialized the formal surface.

Dry-run first:

```powershell
python -m nsgablack catalog cleanup-legacy-postgres --profile framework-core --db-url "postgresql://postgres:YOUR_PASSWORD@localhost:5432/nsgablack"
```

Execute only after the dry-run says `can_execute = true`:

```powershell
python -m nsgablack catalog cleanup-legacy-postgres --profile framework-core --db-url "postgresql://postgres:YOUR_PASSWORD@localhost:5432/nsgablack" --execute --yes
```

Cleanup rules:

- default mode is dry-run only
- actual drop requires both `--execute` and `--yes`
- cleanup checks that the formal persisted surface already exists
- cleanup checks that the requested formal profile already has entry rows
- after cleanup, PostgreSQL materialization no longer recreates the old split tables

Current returned payload shape:

```json
{
  "backend": "postgresql",
  "components": 205,
  "contexts": 205,
  "usages": 205,
  "params": 260,
  "methods": 181,
  "health": 205
}
```

## Dashboard / UI Usage

PostgreSQL-backed dashboard:

```powershell
python -m nsgablack catalog ui --profile framework-core --db-path "postgresql://postgres:YOUR_PASSWORD@localhost:5432/nsgablack" --source-mode only
```

Config-backed dashboard using local `catalog/db.toml`:

```powershell
python -m nsgablack catalog ui --profile framework-core
```

If local PostgreSQL config is enabled, the page will now prefer that configured catalog
store automatically even when you do not pass `--db-path`.

MySQL-backed dashboard:

```powershell
python -m nsgablack catalog ui --profile framework-core --db-path "mysql://root:YOUR_PASSWORD@127.0.0.1:3306/nsgablack" --source-mode only
```

Recommended strict verification flow:

1. materialize the target profile
2. launch dashboard with explicit `--db-path`
3. use `--source-mode only`

That guarantees the page is reading the persisted SQL catalog rather than silently drifting back to registry.

## Recommended PostgreSQL Local Setup

For the current local environment style, the most stable local file is:

```toml
[postgres]
enabled = true
mode = "prefer"
readonly = false
host = "localhost"
port = 5432
user = "postgres"
password = "YOUR_PASSWORD"
database = "nsgablack"
connect_timeout = 10

[mysql]
enabled = false
mode = "prefer"
readonly = false
```

## Verification Checklist

After changing local DB config, verify all four:

1. `python -m nsgablack catalog materialize --profile framework-core --db-url "..."`
2. `python -m nsgablack catalog search vns --profile framework-core`
3. `python -m nsgablack catalog ui --profile framework-core --db-path "..." --source-mode only`
4. `catalog_source_info(...)` reports the expected backend, for example `postgresql`
   and `db_stale == False`

## Troubleshooting

### Problem: UI still looks like registry

Check:

- did you actually materialize the profile first
- are you passing explicit `--db-path`
- are you running with `--source-mode only`
- does `catalog_source_info(...)` show `effective_source = postgresql` or `mysql`
- if `db_stale == True`, materialize the requested profile again; `prefer` deliberately
  refuses to advertise retired entries from an older database snapshot

### Problem: config file exists but is ignored

Check:

- file name is exactly `catalog/db.toml`
- block name is `[postgres]`, `[postgresql]`, or `[mysql]`
- `enabled = true` is set for the intended backend
- you did not accidentally enable both backends

### Problem: PostgreSQL materialize fails on an older DB

The store now creates missing catalog tables and field-value indexes on demand.
If the DB contains old catalog tables but is missing newer index tables, rerun
materialization once with the explicit PostgreSQL URL.

## Related Files

- [catalog/db.toml.example](C:/Users/hp/Desktop/nsgablack/catalog/db.toml.example)
- [catalog/store/__init__.py](C:/Users/hp/Desktop/nsgablack/catalog/store/__init__.py)
- [catalog/store/postgres.py](C:/Users/hp/Desktop/nsgablack/catalog/store/postgres.py)
- [catalog/store/mysql.py](C:/Users/hp/Desktop/nsgablack/catalog/store/mysql.py)
- [catalog/facade.py](C:/Users/hp/Desktop/nsgablack/catalog/facade.py)
- [catalog/DASHBOARD_PROTOCOL.md](C:/Users/hp/Desktop/nsgablack/catalog/DASHBOARD_PROTOCOL.md)
