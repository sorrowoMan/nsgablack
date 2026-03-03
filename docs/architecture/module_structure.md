# NSGABlack 目录结构（当前架构）

本页用于回答“每个目录负责什么”，并明确核心边界。

## 1. 顶层结构
```text
nsgablack/
├── core/                 # 求解器底座 + adapter 体系
├── representation/       # 表示管线与算子
├── bias/                 # 偏置系统
├── plugins/              # 运行能力扩展
├── utils/                # 工程工具、suites、context/snapshot
├── catalog/              # 组件索引与可发现性
├── docs/                 # 文档
└── examples/             # 示例
```

## 2. Core 边界

### 2.1 Solver 层
- `core/blank_solver.py`：`SolverBase`
  只负责控制面：生命周期、stop/step、plugin hook、context/snapshot 读写。
- `core/composable_solver.py`：`ComposableSolver`
  通用执行器，算法通过 adapter 注入。
- `core/evolution_solver.py`：`EvolutionSolver`
  官方进化求解器预置（基于 adapter 体系）。

注意：`core/solver.py` 已删除（断兼容）。

### 2.2 Adapter 层
- `adapters/`
  放算法流程实现（NSGA2/VNS/MOEAD/SA/多策略控制等）。

## 3. Representation / Bias / Plugin
- `representation/`：初始化、变异、修复、编码解码。
- `bias/`：算法偏置与领域偏置，独立模块化。
- `plugins/`：checkpoint、trace、report、并行、导出等运行能力。

## 4. Context 与 Snapshot
- `utils/context/context_store.py`：小字段存储（契约字段、协作字段）。
- `utils/context/snapshot_store.py`：大对象存储（population/objectives/violations 等）。
- 约定：`Context` 放引用，`Snapshot` 放大对象。

## 5. 工程层
- `utils/suites/`：权威组合装配入口（减少漏配）。
- `utils/engineering/`：配置、schema、日志、实验结果等。
- `catalog/`：统一索引与搜索入口。

