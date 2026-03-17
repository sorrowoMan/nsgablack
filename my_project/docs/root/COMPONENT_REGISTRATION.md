# COMPONENT_REGISTRATION

组件注册说明  
This file defines the local project registration contract.

**为什么要注册组件 / Why register components**
- 供 Catalog 与 Run Inspector 发现与审计
- 统一 `build_solver.py` 与 `catalog/project_registry.py` 的入口
- 让 context I/O 更可追踪

**需要注册什么 / What should be registered**
- problem builders
- pipelines / biases / adapters / plugins
- solver assembly entries

原则：仅登记可复用或可发现的组件；实验草稿不必登记。

**在哪里注册 / Where to register**
- Local project entries: `catalog/project_registry.py`
- Catalog key 统一使用 `project.` 前缀

**最小条目契约 / Minimal entry contract**
Each `CatalogEntry` should include:
- `key`, `kind`, `title`, `import_path`
- `tags`, `summary`
- `context_requires`, `context_provides`, `context_mutates`, `context_cache`
- `use_when`, `minimal_wiring`, `required_companions`, `config_keys`, `example_entry`

context 若无任何使用，允许为空 `()` 并在 `context_notes` 说明。

**校验 / Validation**
```powershell
python -m nsgablack project doctor --path . --build --strict
python -m nsgablack project catalog list --path .
python tools/catalog_integrity_checker.py --check-usage --strict-usage --check-context --context-kinds plugin --require-context-notes --strict-context
```

**UI Scope**
- `Scope=project`: local components
- `Scope=framework`: framework built-in components
- `Scope=all`: merged view
