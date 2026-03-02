# COMPONENT_REGISTRATION

本文件定义项目本地组件注册契约。  
This file defines the local project registration contract.

## 为什么要注册 / Why register components
- 让组件可被 Catalog 和 Run Inspector 检索。
- 保持装配可复现（`build_solver.py` + 稳定 key）。
- 让 context 读写可审计（`context_*` 字段）。
- Make components discoverable, reproducible, and auditable.

## 注册什么 / What should be registered
注册可复用、可搜索、可开关的组件：  
Register reusable components that may be searched, toggled, or reused:
- problem builders
- pipelines / biases / adapters / plugins
- solver assembly entries

不要注册一次性脚本或私有调试代码。  
Do not register one-off helpers or private debug code.

## 在哪里注册 / Where to register
- Local project entries: `project_registry.py`
- 本地 key 建议简短；加载器会自动加前缀 `project.`
- Local keys should be short; loader auto-prefixes with `project.`
  (example: `pipeline.example` -> `project.pipeline.example`)

## 最小契约 / Minimal entry contract
Each `CatalogEntry` should include:
- `key`, `kind`, `title`, `import_path`
- `tags`, `summary`
- `context_requires`, `context_provides`, `context_mutates`, `context_cache`
- `use_when`, `minimal_wiring`, `required_companions`, `config_keys`, `example_entry`

- 使用说明字段是可发现性的基础。
- context 字段是契约审计的基础。
- 若省略，框架可能推断默认值，但 CI/doctor 应视为不合规。
- Usage fields are mandatory for discoverability UX.
- Context fields are mandatory for contract auditability.
- If omitted, framework may infer defaults, but CI/doctor should treat this as non-compliant.

context 字段即使为空也显式写 `()`，并始终提供 `context_notes`。  
Keep context fields explicit as `()`, and always provide `context_notes`.

## Example
```python
CatalogEntry(
    key="plugin.eval_cache",
    title="Evaluation Cache Plugin",
    kind="plugin",
    import_path="plugins.eval_cache:EvaluationCachePlugin",
    tags=("project", "plugin", "cache"),
    summary="Cache repeated evaluations by deterministic key.",
    context_requires=("population_ref",),
    context_provides=("context.cache.eval_hits",),
    context_mutates=("context.cache.eval_store",),
    context_cache=("context.cache.eval_store",),
)
```

## 校验 / Validation
修改注册后建议执行：  
Run after changing registry entries:
```powershell
python -m nsgablack project doctor --path . --build --strict
python -m nsgablack project catalog list --path .
python tools/catalog_integrity_checker.py --check-usage --strict-usage --check-context --context-kinds plugin --require-context-notes --strict-context
```

## UI 中的 Scope / Scope in UI
In Run Inspector Catalog tab:
- `Scope=project`: local project components
- `Scope=framework`: framework built-in components
- `Scope=all`: merged view
