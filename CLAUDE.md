# CLAUDE.md

## 位置

- nsgablack（编排层）：`C:\Users\hp\Desktop\nsgablack`
- mlblack（ML 语义层）：`C:\Users\hp\Desktop\mlblack`

**两个框架是一体的**：nsgablack = 外层控制/搜索/编排/多目标/L0 资源；mlblack = 内层 ML 语义（DataView/Spec/Codec/Problem/Trainer/Model）。

**解决问题时必须同时思考两边的组件**：
- nsgablack 有 23 个 Adapter（搜索器）+ Newton/Broyden 解析求解器（Plugin）+ Bias 软约束 + L0 资源调度
- mlblack 有 6 个 AlgorithmAdapter（梯度下降/backprop）+ 24 个 Pipeline 组件 + 270 个组件
- 遇到任何问题，先问：nsgablack 的哪个搜？mlblack 的哪个训？解析解用 Newton 还是 Broyden？
- **禁止只用一边的组件就下结论。** SHAP 的 WLS 有解析解 → 用 Newton/Broyden Plugin 求解，不是用 PatternSearch 瞎搜。
## 双框架 Catalog 规则（最高优先级，强制）
**任何能力分析、组件发现、架构调研、实现规划，必须同时搜索双方 catalog。禁止只搜一边就下结论。**
注意，框架提供了rag库，可用且有效，
| 项目 | 数值 |

|---|---|

| 索引 chunks | 2,033（nsgablack 1,192 + mlblack 841） |

| 搜索引擎 | ✅ 正常工作 |

| 查询举例 | "VNS multi-objective optimization" → 5 条相关结果，最高相似度 0.52 |
    

MCP Server 也已配置为 local_embed=True（mcp_server.py:27），下次重启 Claude Code 时 MCP 会自动连接，你就能直接调 rag_search / rag_status 工具了。


唯一遗憾：sentence-transformers 每次加载模型都要从 HF Hub 验证，耗时 ~2 秒。设个 HF_TOKEN 可以加速，不过不设也完全能用。
```bash
# nsgablack（编排层）
python -m nsgablack catalog search <query> --profile framework-core
python -m nsgablack catalog list --kind <kind> --profile framework-core
python -m nsgablack catalog show <key> --profile framework-core

# mlblack（ML 语义层）—— 也必须搜！
cd C:\Users\hp\Desktop\mlblack
python -m mlblack catalog search <query>
python -m mlblack catalog list --kind <kind>
python -m mlblack catalog show <key>
```

双口径：nsgablack 用 `default`（全量）/ `framework-core`（主干）。

## Catalog 存储规则（强制）

**catalog 查询走 DB（PostgreSQL），不读 `entries.toml`。** TOML 4000+ 行是 token 炸弹。

```bash
# 查询 — 走 DB（catalog CLI 内部走 SQL）
python -m nsgablack catalog show <key> --profile default
python -m nsgablack catalog search <query> --profile default
python -m nsgablack catalog list --kind <kind> --profile default

# 注册新组件 — 走 registry.py 的 _default_entries()，不进 entries.toml
# 注册完同步到 DB：
python -m nsgablack catalog materialize --profile default
```

**禁止：** 直接 Read `entries.toml`；往 `entries.toml` 追加新 entry。

## Catalog 驱动（强制）

所有阶段（调研/规划/探索/新增）**绝不要扫描源文件**，用 catalog 搜索。

| 意图 | 做法 | 禁止 |
|---|---|---|
| 语义搜索 | `rag search "<query>" --kind <kind>` | 全量扫源文件 |
| 了解组件 | `catalog show <key>` | Read 整个源文件 |
| 发现同类 | `catalog list --kind <kind>` | grep/glob 扫描源码 |
| 精确搜索 | `catalog search "<query>"` | Read `entries.toml` 全文 |
| 看算法内部逻辑 | Read 具体文件的具体行范围 | — |

**探索/调研流程：先用 RAG 语义搜索 → 再用 catalog 精确查询 → 最后才 Read 具体行。**

## 常用命令

```
python -m pytest tests/ -x -q
python -m nsgablack rag search "<query>" --kind <kind>           # RAG 语义搜索（优先）
python -m nsgablack rag search "<query>" --framework mlblack     # 跨框架搜索
python -m nsgablack rag index --profile framework-core           # 构建/刷新索引
python -m nsgablack rag status                                   # 索引状态
python -m nsgablack catalog list --kind <kind> --profile framework-core
python -m nsgablack catalog search <query> --profile framework-core
python -m nsgablack catalog show <key> --profile framework-core
python -m nsgablack project doctor --path . --strict --format problem
cd C:\Users\hp\Desktop\mlblack && python -m mlblack catalog list --kind <kind>
cd C:\Users\hp\Desktop\mlblack && python -m mlblack catalog search <query>
cd C:\Users\hp\Desktop\mlblack && python -m mlblack catalog show <key>
```

## 架构（正交五层）

| 层 | nsgablack | mlblack | 职责边界 |
|---|---|---|---|
| 控制平面 | Solver | Trainer | 生命周期，不含算法策略 |
| 策略 | Adapter | OptimizerAdapter | propose/update，不含运行时/日志 |
| 表示 | Representation | ModelRepresentation + Codec + Head | 编码/解码/修复，不含业务策略 |
| 能力 | Plugin | Plugin（统一） | 工程能力，不改写算法语义。mlblack Capability 已归入 Plugin 体系 |
| 软引导 | Bias | OptimizationBias | 软偏好，不替代硬约束 |

## 标准脚手架（强制）

**任何新 example/demo/benchmark 必须走标准脚手架，禁止手创文件。**
**Solver 和 Trainer 使用完全一致统一模板。**

```powershell
# 1. 创建项目
python -m nsgablack project new <project_name>

# 2. 添加 case（solver 或 trainer，模板一致）
cd <project_name>
python -m nsgablack project add-case <case_name> --type solver
python -m nsgablack project add-case <case_name> --type trainer

# 3. 标准结构（自动生成，solver/trainer 完全一致）:
#   build_solver.py    — canonical 装配入口
#   build_trainer.py   — 别名: from .build_solver import build_solver as build_trainer
#   run_solver.py      — CLI 薄入口
#   run_trainer.py     — 别名
#   config.py          — 组件注册
#   problem/           — Problem 定义
#   pipeline/          — 管线（encode/decode/init/mutate/repair + data）
#   adapter/           — Adapter 配置/编排
#   bias/              — 自定义 Bias
#   plugins/           — 自定义 Plugin
#   solver/            — Solver 配置
#   evaluation/        — 评估运行时
#   runtime/           — L0 资源
#   catalog/           — 项目 catalog
#   docs/              — 文档
#   tests/             — 测试

# 3. 验证
python -m nsgablack project doctor --path . --strict
python build_solver.py --check
```

**禁止：手动 mkdir + 手写 build_solver.py、把一个 case 的所有代码挤在单个 run_all.py 里。**

## 统一架构规则（新增）

- Solver = Trainer：同一抽象层级，共享统一脚手架模板。差异仅在 catalog `kind` 字段。
- `build_solver.py` 是唯一 canonical 装配入口；`build_trainer.py` 是薄别名（`from .build_solver import build_solver as build_trainer`）。
- `representation/` 不作为独立目录存在；模型编解码器是 `pipeline/` 的内部组件。
- `assembly/scaffold.json` 已移除；装配逻辑全部进入 `build_solver.py`。
- 统一 Plugin 体系：`nsgablack.plugins.base.Plugin` 包含 10 个钩子超集（含 mlblack 的 `on_evaluate_start/end`、`on_error`）。mlblack 的 `Capability` 已归入 Plugin 体系。
- mlblack 脚手架完全复用 nsgablack 的 `project/scaffold/`，`scaffold_legacy.py` 已删除。

## 边界规则

- Adapter 不含运行时能力；Solver 不含算法策略
- `repair` 仅做约束安全检查，不含业务策略
- 大对象 → SnapshotStore，context 只保留引用（`_ref` / `snapshot_key`）
- Context key 来自 `core/state/context_keys.py`
- 通信面：ResourceContext、内层 payload、artifact/result
- 不在 nsgablack 硬编码 mlblack 内部细节
- 新增 example/case → `examples/cases/<case>/` 标准脚手架，不进 `my_project/`
- Catalog 变更 → 验证 `default` 和 `framework-core` 双口径

## 关键路径

```
nsgablack/
  core/              — Solver、L0 资源调度
  adapters/          — 算法策略（VNS/SPEA2/MOEAD/NSGA2/NSGA3…）
  representation/    — 编码/解码/修复
  plugins/           — 能力层（runtime/eval/system）
  bias/              — 软偏好引导
  catalog/           — 组件注册表（entries.toml + registry.py）
  project/           — 脚手架 + doctor
  examples/cases/    — 标准示例
  my_project/        — 脚手架模板（保持干净，不含示例）

mlblack/
  models/            — Model/Forecast/Distribution/Ensemble/Symbolic/Neural
  pipeline/          — DataPipeline/ModelConditionedTarget/Fusion
  representations/   — Codec/Head/Symbolic
  integrations/      — 跨框架集成（nsgablack_symbolic…）
  problems/          — Problem/SymbolicProblem
  assembly/          — Trainer 装配
  presets/           — 预设配置
  examples/cases/    — ML 示例
```

## 禁止事项

- 只搜 nsgablack catalog 就做架构判断
- 全量读 `entries.toml`（3738 行）或任意大源文件
- 在 `my_project/` 放置 example/case
- Adapter 里写日志/IO；Plugin 里改写搜索语义
- 在 nsgablack 层硬编码 mlblack 的 DataView/Spec/Codec 内部细节
- 把 solver 和 trainer 当成不同目录结构处理（统一模板，`build_solver.py` canonical）
- 创建独立的 `representation/` 目录（编解码器进 `pipeline/`）
- 使用 `assembly/scaffold.json` 配置装配（装配逻辑进 `build_solver.py`）
- 在 mlblack 中使用遗留的 `Capability` 类（统一走 `Plugin`）
