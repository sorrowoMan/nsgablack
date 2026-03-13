# Surrogate Workflow (Capability Layer)

This workflow keeps solver bases pure. Surrogate logic is injected as a plugin.

## Inputs

- A real problem: `BlackBoxProblem.evaluate(x)` (ground truth)
- A solver: `ComposableSolver` or `EvolutionSolver`
- A representation: `RepresentationPipeline` (feasibility first)
- Optional biases: `BiasModule`

## Output

- Faster runs (fewer real evaluations) *or* lower wall-time under same budget
- Unified logs for fair comparison: CSV + summary JSON

## Recommended wiring

1) Build the baseline (no surrogate)

- attach strategy (Adapter/Wiring)
- attach `BenchmarkHarnessPlugin` so every run has the same protocol output

2) Enable surrogate short-circuit

- attach `SurrogateEvaluationPlugin`
- keep `BenchmarkHarnessPlugin` unchanged

3) Compare fairly

- same seed/budget/pipeline/bias/adapter
- only swap surrogate plugin on/off

## Critical Rules (must follow)

### Bias 不在 _true_evaluate 内部 apply

`SurrogateEvaluationPlugin` 的 `_true_evaluate()` **不得**自行调用 `bias_module.compute_bias()`。
由于 surrogate plugin 接管了 `evaluate_population`（solver 原生 bias 路径被跳过），
Bias 由 plugin 在 `evaluate_population` 返回前的 Step 5 统一 apply 一次，避免 double-bias。

具体规则：
- 插件调用并行评估器时，必须传入 `enable_bias=False, bias_module=None`
- 插件内部的 `_true_evaluate()` 返回的是 **raw objectives**（未偏置）
- 训练代理模型的数据必须存储 **raw objectives**，否则模型学到的是被污染的分布

> 参考：`docs/development/DEVELOPER_CONVENTIONS.md` 第 3 节「Bias 统一 apply 规则」

### 实例级 RNG

插件内部如需随机数，使用 `self._rng = np.random.default_rng()`，不使用全局 `np.random`。

## Notes

- Surrogate is not a "core goal" of the framework; it is an optional capability.
- Older experimental surrogate implementations were removed to reduce maintenance
  cost; use git history if you need to inspect them.

