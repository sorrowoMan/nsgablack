# START_HERE — NSGABlack 入口地图

一句话记住：**Problem + Pipeline + Bias + Adapter + Plugin**。  
Solver 只负责生命周期和运行容器。

---

## 1) 推荐起手式：先创建项目骨架（推荐）

在任意目录执行（已 `pip install -e .`）：

```powershell
python -m nsgablack project init my_project
cd my_project
python -m nsgablack project doctor --path . --build
python build_solver.py
```

为什么推荐这条路：
- 自带 `problem/pipeline/bias/adapter/plugins` 结构，不会乱
- 自带 `project_registry.py`，本地组件可被 project catalog 搜到
- `doctor` 可提前暴露接线/契约问题

---

## 2) 新问题最短路径（框架最小闭环）

1. 定义问题接口（Problem）
   - `core/base.py`
2. 选择表征管线（Pipeline，硬约束优先放这里）
   - `representation/`
   - `docs/indexes/REPRESENTATION_INDEX.md`
3. 装配偏置（Bias，软约束/偏好）
   - `bias/`
   - `docs/user_guide/bias_baby_guide.md`
4. 选择策略内核（Adapter）
   - `core/adapters/`
5. 加能力层（Plugin）
   - `plugins/`
6. Solver 组装 + 冒烟验证
   - `build_solver.py`

---

## 3) Catalog 怎么用（含 context 搜索）

全局 Catalog：

```powershell
python -m nsgablack catalog search vns
python -m nsgablack catalog show suite.multi_strategy
python -m nsgablack catalog search context_requires --field context --kind plugin
```

项目 Catalog（本地 + 全局）：

```powershell
python -m nsgablack project catalog list --path my_project
python -m nsgablack project catalog search context_mutates --field context --path my_project --global
```

---

## 4) Run Inspector（结构审计 UI）

统一入口：

```powershell
python -m nsgablack run_inspector --entry path/to/script.py:build_solver
```

你会看到：
- 左侧 Wiring：Solver / Adapter / Pipeline / Bias / Plugin 组件开关
- 中间 History：运行记录
- 右侧 Tabs：Details / Run / Contribution / Trajectory / Catalog / Context

重点：
- `Catalog` Tab 已支持 `Match=context`
- `Context` Tab 直接看运行时字段
- 可用搜索词：`context_requires`、`visualization prior`、`可视化先验`

---

## 5) 工程能力地图（高频）

- 评估能力：`plugins/evaluation/`（surrogate / MC / multi-fidelity）
- 运行能力：`plugins/runtime/`（archive / adaptive / elite / convergence / switch）
- 审计能力：`plugins/ops/`（benchmark / module_report / profiler / sensitivity）
- 系统能力：`plugins/system/`（async_event_hub / boundary_guard / memory）
- 存储能力：`plugins/storage/mysql_run_logger.py`
- 权威组合：`utils/suites/`

---

## 6) 常用工具（tool 层）

- Catalog 导入完整性检查：

```powershell
python tools/catalog_integrity_checker.py
python tools/catalog_integrity_checker.py --check-context
```

- Catalog 构建：`tools/build_catalog.py`
- API 文档生成：`tools/generate_api_docs.py`

---

## 7) 常用索引（找不到就看）

- 单文件总手册：`docs/INDEX_MANUAL.md`
- 端到端流程：`WORKFLOW_END_TO_END.md`
- 功能总览：`docs/FEATURES_OVERVIEW.md`
- 示例总览：`docs/AUTHORITATIVE_EXAMPLES.md`
- context 契约：`docs/user_guide/CONTEXT_CONTRACTS.md`
- Run Inspector 说明：`docs/user_guide/RUN_INSPECTOR.md`
---

## Catalog registration priority / 注册路径优先级（明确）

- Preferred: `catalog/entries.toml` (project local, UI-friendly)  
  首选：`catalog/entries.toml`（项目本地，适合 UI 注册与维护）
- Optional fallback: `project_registry.py`  
  备选：`project_registry.py`（仅用于动态/代码式注册）

Rule of thumb / 经验规则：
- Static, searchable component metadata -> `entries.toml`
- Dynamic programmatic registration -> `project_registry.py`
