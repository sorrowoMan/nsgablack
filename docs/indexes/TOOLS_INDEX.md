# 工具索引（对齐当前架构）

这份索引回答两类问题：

1) “我要找某个能力/组件，它在哪？”
2) “有哪些脚本/工具可以帮助我维护与验证工程？”

如果你只想快速定位：优先用 Catalog（可发现性层）：

```bash
python -m nsgablack catalog search vns
python -m nsgablack catalog list --kind plugin
python -m nsgablack catalog show adapter.sa
```

---

## 1) 工程维护脚本（tools/ 与 scripts/）

- `tools/build_catalog.py`：构建/更新工程索引类文件（如果你仍需要静态索引）
- `tools/generate_api_docs.py`：生成 API 文档
- `utils/viz/visualizer_tk.py`：Run Inspector（运行前审查 wiring + 缺失伙伴提示）
  - 统一入口：`python -m nsgablack run_inspector --entry path/to/script.py:build_solver`
- `tools/context_field_guard.py`：Context 字段治理守卫（检查 catalog/契约中的非 canonical key）
  - 用法：`python tools/context_field_guard.py --strict`
- `tools/schema_tool.py`：JSON 产物 schema 版本校验
  - 用法：`python tools/schema_tool.py runs/ --strict`
- `tools/release/make_v010_repro_package.py`：构建可复现发布包（docs + baseline + manifest）
  - 用法：`python tools/release/make_v010_repro_package.py --tag v0.10.0`
- `tools/cleanup_project.py`：清理工程杂项/归档
- `scripts/organize_project.py`：项目结构整理脚本（如有）

---

## 2) 核心工程基础设施（utils/）

- `utils/extension_contracts.py`：扩展点契约护栏（shape/语义/副作用边界）
- `core/state/context_schema.py`：context 最小 schema（用于扩展点一致性）
- `core/state/context_keys.py`：常用 context key 常量（避免各模块各写字符串）
- `plugins/`：插件系统（日志/调参/评估短路/并行调用等）
- `utils/wiring/`：权威组合（attach_* 一键装配，避免漏配）
- `utils/parallel/evaluator.py`：并行评估工具（推荐 `from nsgablack.utils.parallel import ParallelEvaluator`）
- `utils/parallel/integration.py`：并行评估集成（保持 solver 底座纯净）
- `representation/ParallelRepair`：可选的 repair 并行封装（修复阶段并行化）
- `utils/engineering/logging_config.py`：日志配置
- `utils/engineering/file_io.py`：原子写入 JSON（`atomic_write_json`）
- `utils/engineering/schema_version.py`：JSON 产物 schema 版本戳/校验（`stamp_schema` / `schema_check`）
- `core/state/context_contracts.py`：组件契约收集与冲突检测
- `core/state/context_field_governance.py`：字段治理（canonical key 校验）

---

## 3) 目录边界提示（避免找错）

- Core（稳定承诺）：`core/`、`representation/`、`bias/`、`utils/`、`catalog/`
- 历史/实验内容：本仓库已清理相关目录以降低维护成本；如需追溯请查看 git 历史

边界说明见：`docs/CORE_STABILITY.md`
