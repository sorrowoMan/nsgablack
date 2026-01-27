# START_HERE — NSGABlack 入口地图

一句话记住：**问题接口 + 表征管线 + 偏置策略 + 求解器入口**。

---

## 1) 新问题最短路径（10 分钟跑通）

1. 定义问题接口
   - `core/base.py`
2. 选择表征管线（变量类型）
   - `representation/`
- `docs/indexes/REPRESENTATION_INDEX.md`
3. 选择偏置（策略/规则/代理控制）
   - `bias/bias.py`
   - `docs/user_guide/bias_baby_guide.md`
4. 选择求解器入口  
   - 标准多目标（NSGA-II 底座）：`core/solver.py`（`BlackBoxSolverNSGAII`）  
   - 可组合/可融合（Adapter 驱动）：`core/composable_solver.py` + `core/adapters/` + `utils/suites/`  
   - 特殊流程/非进化原型：`core/blank_solver.py` + `utils/plugins/`  
   - 多策略协同/多角色并行：`core/adapters/multi_strategy.py` + `utils/suites/multi_strategy.py`  
5. 冒烟验证（确认框架可用）

---

## 2) 我该选哪个入口？

- **标准多目标优化**：`core/solver.py`
- **昂贵评估/代理加速（能力层，不污染底座）**：`utils/plugins/surrogate_evaluation.py`
- **多策略并行协同（进阶能力）**：`core/adapters/multi_strategy.py`
- **算法/业务偏置驱动**：`bias/`、`docs/user_guide/bias_system.md`
- **想快速看 API 入口**：`docs/user_guide/external_api_navigation.md`

---

## 3) 常用“找不到就看这里”

- 工具索引：`docs/indexes/TOOLS_INDEX.md`
- 表征索引：`docs/indexes/REPRESENTATION_INDEX.md`
- 算法拆解原则（总纲）：`DECOMPOSITION_RULES.md`
- 权威现代示例（事实标准）：`docs/AUTHORITATIVE_EXAMPLES.md`
- 端到端落地流程（面对一个问题怎么做）：`WORKFLOW_END_TO_END.md`
- 扩展点契约（护栏）：`docs/user_guide/EXTENSION_CONTRACTS.md`
- Catalog / Suites（可发现性 + 权威组合）：`docs/user_guide/catalog.md`
- Core 稳定性与边界说明：`docs/CORE_STABILITY.md`
- 详尽说明书：`docs/project/PROJECT_DETAILED_OVERVIEW.md`
- 标签化目录：`docs/indexes/TAGGED_INDEX.md`

---

## 5) 常用工具（懒人优先）

- 生成目录索引：`tools/build_catalog.py`
- 生成 API 文档：`tools/generate_api_docs.py`
