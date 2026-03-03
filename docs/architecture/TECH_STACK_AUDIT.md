# TECH_STACK_AUDIT

> NSGABlack 技术栈、架构设计与解耦审查（中英双语）  
> NSGABlack Technical Stack, Architecture, and Decoupling Audit (Bilingual)

## 0) 元信息 / Metadata

- 审查日期（Date）: 2026-03-02
- 审查范围（Scope）: 当前仓库主代码路径（`core/`, `representation/`, `bias/`, `plugins/`, `utils/`, `catalog/`, `project/`, `utils/viz/`）
- 审查方法（Method）:
  - 静态代码与文档审阅（Static code/doc review）
  - 工程治理能力检查（contracts/catalog/doctor/ui）
  - 测试结果参考（latest full test run）
- 测试基线（Test baseline）: `323 passed, 2 skipped`

---

## 1) 执行摘要 / Executive Summary

### 中文
- 框架已形成“控制面 + 数据面 + 组件面 + 治理面”的清晰分层。
- `ContextStore`（小字段）与 `SnapshotStore`（大对象）的职责分离是当前架构的关键优势。
- `Catalog + Contract + Doctor + Run Inspector` 构成了较完整的工程闭环（发现、装配、诊断、观测、复现）。
- 主要技术债不在算法抽象，而在：
  - `legacy solver` 与新 solver-control-first 路径并存导致心智负担；
  - 部分路径“宽异常吞掉”影响可观测性；
  - 文档/编码一致性存在工程噪音。

### English
- The framework now has a clear layered model: control plane, data plane, component plane, and governance plane.
- The split between `ContextStore` (small contract fields) and `SnapshotStore` (large artifacts) is a major architectural strength.
- `Catalog + Contract + Doctor + Run Inspector` provides a strong engineering loop (discover, wire, diagnose, observe, reproduce).
- Main debt is not algorithm abstraction; it is:
  - coexistence of legacy solver and solver-control-first path,
  - broad exception swallowing in some paths reducing observability,
  - documentation/encoding consistency noise.

---

## 2) 技术栈盘点 / Tech Stack Inventory

### 2.1 语言与核心依赖 / Language & Core Dependencies
- Python: `3.8 ~ 3.13`（`pyproject.toml`）
- Core scientific stack:
  - `numpy`
  - `scipy`
  - `scikit-learn`
- 可选依赖 / Optional:
  - `redis`（Context/Snapshot backend）
  - `ray`, `joblib`（并行/分布式可选）
  - `skopt`（Bayesian optional）

### 2.2 存储与序列化 / Storage & Serialization
- Context backends: memory / redis（`utils/context/context_store.py`）
- Snapshot backends: memory / redis / file(npz + meta + extras)（`utils/context/snapshot_store.py`）
- Serialization formats:
  - JSON / JSONL（运行产物、trace、bundle）
  - TOML（catalog entries）
  - pickle（redis payload，internal trusted path）
  - NPZ（大数组快照）

### 2.3 UI 与可观测性 / UI & Observability
- Run Inspector（Tkinter）: `utils/viz/app.py`, `utils/viz/ui/*`
- Observability plugins:
  - `decision_trace`
  - `sequence_graph`（List / Trie / Trace）
  - `profiler`
  - `benchmark_harness`
  - `module_report`
  - `pareto_archive`

### 2.4 工程与质量 / Engineering & Quality
- Test: `pytest`
- Style/lint/type: `black`, `flake8`, `mypy`
- Coverage: `coverage`
- Governance tools:
  - project doctor: `project/doctor.py`
  - context field guard: `tools/context_field_guard.py`
  - catalog integrity tools

---

## 3) 架构与模块边界 / Architecture and Module Boundaries

### 3.1 控制面（Control Plane）
- `core/blank_solver.py` -> `SolverBase` control-plane methods
- 负责生命周期、状态组织、context 构建、snapshot 持久化入口。

### 3.2 数据面（Data Plane）
- `ContextStore`: 小字段、契约字段、引用字段。
- `SnapshotStore`: population/objectives/violations/pareto/history/trace 等大对象。
- 结论 / Conclusion:
  - “小对象进 Context，大对象进 Snapshot”的边界明确且正确。

### 3.3 组件面（Component Plane）
- `Problem`: 目标/约束定义。
- `Representation`: initializer/mutator/repair/codec。
- `Bias`: 软偏置与策略倾向。
- `Adapter`: propose/update 搜索内核。
- `Plugin`: 可插拔工程能力与观测能力。

### 3.4 治理面（Governance Plane）
- `Catalog`: 发现与可组装目录（含 context/usage 元数据）。
- `Doctor`: 静态 + 运行态规则审查（contracts/snapshot/runtime misuse）。
- `Run Inspector`: 结构与运行过程可视化诊断界面。

---

## 4) 代码级设计与解耦机制 / Code-level Design and Decoupling Mechanisms

### 4.1 关键设计模式 / Key Design Patterns
- Strategy:
  - Adapter 抽象和多策略组合（`adapters/algorithm_adapter.py`）
- Facade:
  - `BiasModule` 封装 manager、缓存、上下文绑定（`bias/bias_module.py`）
- Event Bus / Hook:
  - `PluginManager.trigger/dispatch` + short-circuit（`plugins/base.py`）
- Port + Backend swap:
  - `ContextStore` / `SnapshotStore` 抽象工厂
- Contract-first:
  - `context_requires/provides/mutates/cache` 声明式契约
- Governance-as-code:
  - Doctor 规则与诊断码体系（`project/doctor.py`）

### 4.2 运行交互契约 / Runtime Interaction Contract
- 推荐大对象读写入口：
  - `solver.read_snapshot()`
  - `Plugin.resolve_population_snapshot()`
  - `Plugin.commit_population_snapshot()`
- 设计收益 / Benefit:
  - 降低组件间隐式耦合
  - 后端切换不改组件业务代码

### 4.3 当前 Doctor 规则覆盖（摘要） / Current Doctor Rule Coverage (Summary)
- 契约相关 / Contract:
  - `class-contract-missing`
  - `class-contract-core-missing`
  - `contract-key-unknown`
  - `contract-impl-mismatch`
- Snapshot/Context 相关 / Snapshot-Context:
  - `context-large-object-write`
  - `snapshot-ref-empty`
  - `snapshot-ref-missing`
  - `snapshot-ref-consistency`
  - `snapshot-payload-integrity`
- Runtime misuse:
  - `runtime-bypass-write`
  - `solver-mirror-write`
  - `plugin-direct-solver-state-access`

---

## 5) 工程成熟度评估 / Engineering Maturity Assessment

### 中文结论
- 架构清晰度: 高（High）
- 解耦完整度: 高（High）
- 可观测性: 高（High）
- 可治理性: 高（High）
- 维护门槛: 中（Medium）
- 主要原因：功能层次多、规则体系强，但需要文档与路径收敛来降低新成员学习成本。

### English Conclusion
- Architecture clarity: High
- Decoupling completeness: High
- Observability: High
- Governance: High
- Maintenance barrier: Medium
- Why: rich modularity and strong guardrails are in place, but onboarding cost remains non-trivial without doc/path consolidation.

---

## 6) 主要风险与技术债 / Main Risks and Technical Debt

1. 双路径并存（legacy + solver-control-first）
- 现象 / Symptom: `core/solver.py` 与 `core/blank_solver.py` 同时承载核心语义。
- 风险 / Risk: 新能力落点不统一，团队贡献容易分叉。

2. 部分宽异常处理
- 现象 / Symptom: 若干路径中 `except Exception: pass/return`。
- 风险 / Risk: 系统“可运行”但故障不可见，定位成本上升。

3. 序列化安全边界
- 现象 / Symptom: Redis payload 使用 `pickle`。
- 风险 / Risk: 在不可信输入环境下存在反序列化风险（trusted internal path 可接受）。

4. 文档与编码一致性
- 现象 / Symptom: 部分文档存在乱码/编码不一致噪音。
- 风险 / Risk: 降低对外可信度与团队知识传递效率。

---

## 7) 优先级建议 / Priority Recommendations

### P0（短期，建议立即执行） / P0 (Immediate)
1. 统一 solver-control-first 规范落点  
CN: 新增能力默认落在 `SolverBase` 控制面与 context/snapshot 契约，legacy 路径仅做兼容。  
EN: Default new capabilities to solver-control-first path; keep legacy path compatibility-only.

2. 清理文档编码与术语一致性  
CN: 先修核心入口文档（`README.md`, `START_HERE.md`, `docs/architecture/*`）。  
EN: Fix encoding and terminology consistency for entry docs first.

### P1（中期） / P1 (Mid-term)
1. 异常策略分层  
CN: 区分“可降级异常”与“必须暴露异常”，并统一日志等级。  
EN: Split degradable vs must-surface exceptions; standardize logging levels.

2. 可选安全序列化后端  
CN: 为 Snapshot/Context 引入非 pickle 安全模式（如 JSON/msgpack for safe subset）。  
EN: Add non-pickle safe mode for untrusted contexts (safe subset serialization).

### P2（后续优化） / P2 (Later)
1. 性能画像标准化  
CN: 通过 profiler 形成“热点迁移建议流程”（Python -> native extension optional）。  
EN: Standardize hotspot-driven optimization workflow before any native migration.

2. 架构 ADR 完整化  
CN: 对 Context/Snapshot、Doctor、Repro Bundle、Sequence Trace 持续固化 ADR。  
EN: Keep architecture decisions codified in ADRs for future contributors.

---

## 8) 总结 / Final Assessment

### 中文
这是一个“研究框架工程化”程度很高的架构：  
它的核心价值不只是算法集合，而是可组合、可诊断、可复现、可治理的系统化能力。  
当前阶段最重要的是“收敛路径与提升可维护性”，不是继续扩张抽象层数。

### English
This framework is already strong in engineering maturity for a research-oriented optimizer stack.  
Its main value is not only algorithms, but system capabilities: composability, diagnosability, reproducibility, and governance.  
At this stage, the highest ROI is path consolidation and maintainability, not adding more abstraction layers.

