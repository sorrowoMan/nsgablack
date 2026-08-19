# 组件注册规范

本文件定义 Case 本地组件的 Catalog 注册契约。

## 为什么注册

- 让 Catalog、Doctor 与 Run Inspector 发现真实装配能力。
- 保持 `build_solver.py` 与 `catalog/entries/<kind>.toml` 一致。
- 让 Context 输入、输出和副作用可以审计。

## 注册范围

Problem、Pipeline、Bias、Adapter、Plugin 以及正式 Solver/Trainer 装配入口都应注册。静态条目的唯一事实源是 `catalog/entries/<kind>.toml`，不得再维护 Python 注册表或聚合 TOML 副本。

每项至少声明：

- `key`、`kind`、`title`、`import_path`、`tags`、`summary`
- `context_requires`、`context_provides`、`context_mutates`、`context_cache`、`context_notes`
- `use_when`、`minimal_wiring`、`required_companions`、`config_keys`、`example_entry`

## 验证
```powershell
python -m nsgablack project doctor --path . --build --strict
python -m nsgablack project catalog list --path .
```
