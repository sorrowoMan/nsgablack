# plugins

工程插件层：日志、并行、监控、回放、存储。  
Engineering plugin layer: logging, parallelism, monitor, replay, storage.

## 说明 / Notes
- 插件聚焦工程能力，不承载核心问题建模。
- 每个插件尽量显式声明 context 契约。
- Keep plugins focused on capabilities, not core problem modeling.
- Prefer explicit context contracts for each plugin.

## 常用起步项 / Typical starters
- `BenchmarkHarnessPlugin`
- `ModuleReportPlugin`
- `BoundaryGuardPlugin`
