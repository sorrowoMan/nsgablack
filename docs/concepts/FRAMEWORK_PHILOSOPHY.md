# NSGABlack 框架理念与设计理由

一句话定位：NSGABlack 是统一框架栈里的优化搜索语义层，是一个“基于算法解构的可重组优化系统”。

当前第一原则：

- `nsgablack` 与 `mlblack` 共享 Project / Case / Scaffold / L0 substrate。
- `nsgablack` 负责 Solver / Adapter / Representation / Bias / Plugin / Pareto 等优化搜索语义。
- `mlblack` 负责 Trainer / DataView / Spec / Codec / Head / Artifact 等机器学习语义。
- 编排、资源授权、嵌套 Case 调用属于 substrate，不属于任一语义层的私有能力。

这里的“算法解构”不是指强行规定拆法，而是提供足够通用的扩展点，让同一算法可以从不同维度被拆开、复用、再拼装：
- 表示与算子维度：`RepresentationPipeline`（编码/初始化/变异/修复/解码）
- 偏好与软约束维度：`BiasModule` / `UniversalBiasManager`（奖励/惩罚/阶段调度/搜索倾向）
- 搜索策略维度：`AlgorithmAdapter` / `CompositeAdapter`（propose/update）
- 横切能力维度：`Plugin` / `PluginManager`（日志、早停、短路评估、checkpoint、实验追踪等）
- 编排与资源维度：Project / Case / L0 substrate（stage、group、fanout、ResourceContext、nested Case）

## 愿景

- 任何优化算法都能接入，且接入成本低。
- 算法之间可以轻松融合，支持“组合式”构建。
- 一次实现、多处复用，避免为每个新算法重写基础设施。

## 设计原则

1. 解耦：问题定义、流程控制、表示编码、策略偏好、辅助能力相互独立。
2. 可选：偏置、管线、插件都是可选模块，不强制绑定到某种算法。
3. 可组合：多个偏置、多个适配器、多个插件可以组合工作。
4. 可迁移：旧结构可以保留兼容入口，但正式入口收敛到 Project / Case / Scaffold。
5. 可编排：多 solver、多 trainer、嵌套评估和资源授权由 substrate 表达，而不是塞进某个算法层。

## 分层结构

### 1) 问题层（Problem）
- 统一入口：`BlackBoxProblem`。
- `evaluate()` 为必须实现。
- `evaluate_constraints()` 可选；硬约束更推荐放在管线修复，软约束放偏置。

### 2) 求解器层（Solver Bases）
- 标准求解器：`EvolutionSolver`（固定流程）。
- 空白底座：`SolverBase`（不提供流程，完全由插件/子类实现）。
- 可组合求解器：`ComposableSolver`（流程由 Adapter 驱动，评估/调度由底座统一处理）。

### 3) 表示层（Representation Pipeline）
- 负责编码/初始化/变异/修复/解码。
- 特别适合承载硬约束与可行解构造。

### 4) 偏置层（Bias System）
- 表达软约束与搜索倾向（奖励/惩罚/偏好）。
- 适合表达“方向性策略”，不适合接管“硬流程”。

### 5) 插件层（Plugins）
- 负责流程外能力：日志、监控、早停、短路评估、checkpoint、report、backend 接入。
- 插件可以观察和增强生命周期，但不拥有跨 Case 编排和全局资源授权。

### 6) 算法适配层（Algorithm Adapter）
- 只处理“提出候选 + 消化反馈”。
- 让算法逻辑模块化，便于复用、组合、对比。

### 7) 共享 substrate（Project / Case / Scaffold / L0）
- Project 负责跨 Case 顺序、并行、资源池和正式入口。
- Case 是一个独立 Solver / Trainer / evaluator scaffold。
- L0 发放 `ResourceContext`，Case 只消费 grant 和输出 audit。

## 典型工作流程

1. 定义问题（`BlackBoxProblem`）。
2. 选择底座：
   - 固定流程：`EvolutionSolver`
   - 特殊流程：`SolverBase`
   - 可组合算法：`ComposableSolver`
3. 装配模块：
   - 表示管线（编码/初始化/修复）
   - 偏置系统（软约束/方向性引导）
   - 插件（日志、调度、早停、阶段切换）
4. 在 Project 层声明 stages/groups/L0 resource grant。
5. 运行并收集结果。

## “该放在哪里”的选择指南

- 编码/操作算子 → 表示管线
- 硬约束/可行化 → 管线修复或流程拒绝
- 软约束/偏好 → 偏置
- Case 内搜索流程控制（接受准则/阶段切换） → Adapter 或插件
- 跨 Case 编排和资源授权 → Project / L0 substrate
- 可复用算法逻辑 → Adapter
- 一次性特殊流程 → SolverBase + 插件

## 为什么这样设计

- 可复用性更强：算法逻辑、编码、约束、策略可以分别复用。
- 融合更容易：组合适配器可以把多个算法并行/串联融合。
- 协作更清晰：每个模块专注做一件事，减少相互污染。

## 约束策略建议

- 硬约束：优先在管线修复或流程拒绝。
- 软约束：放偏置，支持权重与阶段调度。
- 混合约束：硬约束先保证可行，再用偏置做优化倾向。

## 复用与融合

- 偏置复用：同一偏置可跨算法共享。
- 管线复用：同一编码/修复可跨算法共享。
- 算法复用：Adapter 作为可复用模块，可组合为新算法。

## 取舍

- 解耦与可组合提高了复用能力，但理解成本更高。
- 适配器和插件提供了两条路线：
  - 简单直观 → SolverBase + 插件
  - 工程化复用 → ComposableSolver + Adapter

