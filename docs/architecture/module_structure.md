# NSGABlack 目录结构（对齐当前架构）

本页用于回答“每个文件夹主要装什么”。它以**当前代码为准**，并明确 Core / Experimental / Legacy 的边界。

更强的边界说明见：
- `docs/CORE_STABILITY.md`

---

## 1) 顶层结构（简化版）

```
nsgablack/
├── core/                 # 求解器底座 + Adapter 体系（核心承诺）
├── representation/       # 表示管线与算子（核心承诺）
├── bias/                 # 偏置系统（核心承诺）
├── utils/                # 工具/插件/套件/护栏（核心承诺）
├── catalog/              # 可发现性层（where is X?）
├── examples/             # 2~3 个权威现代示例（事实标准）
└── deprecated/legacy/     # 历史/过渡内容（不再维护；仅兼容/考古）
```

---

## 2) Core（稳定承诺）

### 2.1 `core/`（求解器底座与策略内核）

- `core/solver.py`：`BlackBoxSolverNSGAII`（NSGA-II 底座）
- `core/blank_solver.py`：`BlankSolverBase`（空白底座，流程由 Plugin/子类驱动）
- `core/composable_solver.py`：`ComposableSolver`（Adapter 驱动底座）
- `core/adapters/`：算法策略内核（VNS/MOEA-D/SA/角色控制等）

### 2.2 `representation/`（表示与算子）

- `representation/base.py`：`RepresentationPipeline`（initializer/mutator/repair/encoder 等）
- `representation/*`：连续/整数/二进制/排列/图/矩阵 等算子
- `representation/context_mutators.py`：按 context 切换/调参的 mutator wrapper（例如 VNS/SA 的“阶段信号”）

### 2.3 `bias/`（偏置系统）

- `bias/core/`：偏置基类、管理器、上下文协议
- `bias/algorithmic/`：算法偏置（策略倾向、调度、软约束）
- `bias/domain/`：领域偏置（业务规则）

### 2.4 `utils/`（横切能力与基础设施）

- `utils/plugins/`：插件系统（日志/调参/并行评估调用/评估短路等）
- `utils/suites/`：权威组合（attach_* 一键装配，避免漏配）
- `utils/parallel/evaluator.py`：并行评估工具（推荐 import：`from nsgablack.utils.parallel import ParallelEvaluator`）
- `utils/extension_contracts.py`：扩展点契约护栏（可执行约定）

---

## 3) Experimental（实验探索）

早期 experimental 目录已清理。新想法推荐先以 `Plugin/Suite` 形式落地（能力层），稳定后再进入 Core。

稳定后再迁入 Core，并补齐：suite + catalog + tests。

---

## 4) Legacy（历史归档）

早期 deprecated/legacy 目录已清理。如需追溯，请查看 git 历史。
