# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project aims to follow SemVer.

## [Unreleased]

### Added
- API stability policy and release process documentation.
- Pipeline repair guardrails: ComposableSolver uses repair_batch when available; NSGA-II evaluates repaired candidates.
- ParallelRepair wrapper for optional parallel repair_batch (thread/process).
- Context field governance guard (`tools/context_field_guard.py`) and CI gate.
- Fixed baseline benchmark runner (`benchmarks/fixed_baseline_runner.py`) and evidence protocol doc.
- Repro package builder (`tools/release/make_v010_repro_package.py`).
- Run Inspector Context regression tests (`tests/test_context_view_flow.py`).
- `docs/development/DEVELOPER_CONVENTIONS.md`：State Governance + RNG 规范 + Bias 统一 apply 规则。
- `docs/concepts/CONTEXT_SCHEMA.md`：修复乱码，重写为可读中文。

### Changed
- Project doctor strict mode escalates missing contracts as errors.
- Run Inspector Context panel gains throttled refresh, local cache, and in-UI error visibility.
- State Governance 双轨制：`resolve_population_snapshot()` (读) + `commit_population_snapshot()` (写)，消除 solver mirror write。
- Doctor `--strict` 新增两条守卫规则：`solver-mirror-write` + `plugin-direct-solver-state-access`。
- MOEA/D 修复：per-candidate mode + batch subproblem projection (M-04/M-05)。
- AdaptiveBias weight_cap 限制 + 多样性采样优化 (M-09/M-10)。
- 并行评估器 executor 生命周期统一 (M-11)。
- UniversalBias / DomainBias bias_history 改为 bounded deque + 真实违反率 (M-15/M-16)。
- UI 热重载改为 hash+invalidate (M-13)。ContextView 缓存改为 weakref (M-14)。
- memory_manager 历史采样恢复时序 (M-12)。

### Deprecated
- (fill in as you cut releases)

### Removed
- (fill in as you cut releases)

### Fixed
- **N-01/N-02 (🔴)**: SurrogateEvaluation double-bias + 训练数据污染。`_true_evaluate()` 不再 apply bias；并行路径传入 `enable_bias=False`。
- **N-03**: 6 个 adapter 补齐 `set_state()` 对称实现（moa_star/sa/mas/astar/trust_region_subspace/trust_region_nonsmooth）。
- **N-04**: MOA\* `_labels` dict 追加 `.pop()` 清理，消除内存泄漏。
- **N-05**: SA/SingleTrajectoryAdaptive/AsyncEventDriven 3 个 adapter 改用实例级 `self._rng`。
- **N-06**: representation 模块 30+ 处全局 `np.random` 替换为实例级 `self._rng`（base/continuous/binary/permutation/matrix/integer/graph）。
- **N-07**: `checkpoint_resume.py` 的 `pickle.load` 添加安全注释 `# SECURITY NOTE` + `# nosec B301`。
- **N-10**: MultiFidelityEvaluation 补计 low-fidelity 调用次数。
- **C-01**: MonteCarlo 插件不再污染全局 `np.random` 种子。
- **C-02**: MySQL run_id 改从 context 读取。
- **C-03**: DE bias 使用正确的 fitness 数据源。
- **C-04**: MetaLearning import 路径修正。
- **C-05**: AdaptiveBias 匹配逻辑一致化。
- **C-06**: Plugin dispatch 不再静默吞异常。
- **C-07**: Adapter `__setattr__` 与 dataclass 兼容。
- **C-08~12**: Context-ification 全套，消除 solver mirror write。
