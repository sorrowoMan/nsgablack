# 开发者规范（Developer Conventions）

本文档记录框架内部的三条核心约定。所有新增 adapter / plugin / representation 组件**必须**遵守。

---

## 1. State Governance — 状态读写双轨制

### 规则

| 操作 | 方法 | 含义 |
|------|------|------|
| **读种群** | `solver.read_snapshot()` / `Plugin.resolve_population_snapshot(solver)` | 快照优先：snapshot store → adapter → solver |
| **写种群** | `Plugin.commit_population_snapshot(solver, pop, obj, vio)` | 回写到 adapter（优先）和 solver |

### 为什么

- 防止 plugin 和 adapter 同时直接写 `solver.population`，导致状态竞争。
- adapter 持有自己的内部种群（如 MOEA/D 的子问题种群），是第一责任人。
- solver 级别的 `population` / `objectives` 只作为 fallback 和外部可见快照。

### 怎么做

```python
# ✅ 正确：通过治理函数读写
data = solver.read_snapshot() or {}
pop = data.get("population", [])           # 读
obj = data.get("objectives", [])
vio = data.get("constraint_violations", [])

# ❌ 错误：直接写 solver 内部数组
solver.population = new_pop        # Doctor --strict 会报 solver-mirror-write
solver.objectives = new_obj
```

### Doctor 检查

`python -m nsgablack project doctor --strict` 会检查两条规则：

| 错误码 | 含义 |
|--------|------|
| `solver-mirror-write` | plugin/adapter 直接赋值 `solver.population` 或 `solver.objectives` |
| `plugin-direct-solver-state-access` | plugin 直接读写 solver 的内部状态属性 |

---

## 2. RNG 规范 — 禁用全局随机数

### 规则

所有随机操作**必须**使用实例级 `np.random.Generator`，**禁止**使用全局 `np.random.*`。

### 为什么

- 全局 `np.random` 是进程共享状态，并行实验或多实例运行时会互相污染。
- 无法通过 seed 精确复现某个组件的随机序列。
- `np.random.default_rng()` 是 NumPy 推荐的新 API（自 1.17+）。

### 怎么做

**dataclass 组件**（representation / bias 等）：

```python
@dataclass
class MyMutation(RepresentationComponentContract):
    sigma: float = 0.1

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def mutate(self, x, context=None):
        return x + self._rng.normal(0.0, self.sigma, size=x.shape)  # ✅
        # return x + np.random.normal(0.0, self.sigma, size=x.shape)  # ❌
```

**普通类**（adapter / plugin 等）：

```python
class MyAdapter(AlgorithmAdapter):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._rng = np.random.default_rng()
```

### API 对照

| 旧（禁用） | 新（使用 `self._rng`） |
|---|---|
| `np.random.random()` | `self._rng.random()` |
| `np.random.rand(n)` | `self._rng.random(n)` |
| `np.random.uniform(a, b, n)` | `self._rng.uniform(a, b, n)` |
| `np.random.normal(0, s, n)` | `self._rng.normal(0, s, n)` |
| `np.random.choice(arr, ...)` | `self._rng.choice(arr, ...)` |
| `np.random.randint(a, b)` | `self._rng.integers(a, b)` |
| `np.random.shuffle(arr)` | `self._rng.shuffle(arr)` |
| `np.random.permutation(n)` | `self._rng.permutation(n)` |

### get_state / set_state 对称性

如果你的组件有 `get_state()` 用于 checkpoint，**必须**同时实现 `set_state()`：

```python
def get_state(self) -> dict:
    return {"temperature": self._temperature, "rng": self._rng.__getstate__()}

def set_state(self, state: dict) -> None:
    self._temperature = state["temperature"]
    self._rng.__setstate__(state["rng"])
```

---

## 3. Bias 统一 Apply 规则

### 规则

**`_true_evaluate()` 内部不得 apply bias。** Bias 在每个候选解的评估生命周期中只 apply 一次。

- 若 solver **自行**评估（无 plugin 接管），bias 在 solver 的评估路径末尾 apply。
- 若评估类 plugin **接管** `evaluate_population`（如 SurrogateEvaluation），plugin 需在 `evaluate_population` 返回前统一 apply 一次 bias（因为 solver 的原生 bias 路径被跳过了）。

### 为什么

- 如果 `_true_evaluate()` 内部 apply 了一次 bias，再在末尾 apply 一次，就会产生 **double-bias**。
- 训练数据（如代理模型的训练集）应存储**原始未偏置的目标值**，否则模型学到的是偏置后的分布。

### 怎么做

```python
# ✅ 评估插件内部：只算原始目标值
def _true_evaluate(self, solver, x):
    return solver.problem.evaluate(x)   # 原始值，不加 bias

# ✅ 评估插件末尾或 solver 外层：统一 apply
for i in range(n):
    ctx = solver.build_context(individual_id=i, ...)
    if solver.enable_bias and solver.bias_module:
        objectives[i] = solver._apply_bias(objectives[i], X[i], i, ctx)
```

```python
# ❌ 评估插件内部 apply bias（会导致 double-bias）
def _true_evaluate(self, solver, x):
    raw = solver.problem.evaluate(x)
    return solver._apply_bias(raw, x, 0, ctx)   # 不要这样做！
```

### 并行评估路径

如果评估插件使用 `ParallelEvaluator`，需要显式禁用 bias：

```python
results = evaluator.evaluate(
    solver, candidates,
    enable_bias=False,      # ← 禁用
    bias_module=None,       # ← 禁用
)
```

---

## 速查清单

新增组件前过一遍：

- [ ] 所有随机操作用 `self._rng`，不用 `np.random`
- [ ] 有 `get_state()` 就必须有 `set_state()`
- [ ] 不在评估插件内部 apply bias
- [ ] 种群读写走 `resolve/commit_population_snapshot`
- [ ] 声明了 `context_requires` / `context_provides` / `context_mutates`
- [ ] `python -m nsgablack project doctor --strict` 通过


---

## 4. Run Inspector 与 `build_solver()` 约定

Run Inspector 的 `Load` 会显式调用 `build_solver()` 完成 wiring。  
因此 `build_solver()` 必须是“轻量装配函数”，重计算必须延迟到 `run()` / `evaluate()` 阶段。

### 必须遵守

- `build_solver()` 只做装配：创建 `problem / pipeline / adapter / plugins` 并连接关系。
- 不在 `build_solver()` 里执行基线求解、批量评估、数据导出、模型训练等重任务。
- 将重任务放到 `run()`、`evaluate()`、`on_generation_start()` 或显式的 lazy 初始化函数里。
- 如需基线结果，采用 `_ensure_baseline_output()` 之类的惰性方法按需计算。

### 为什么

- 避免 UI `Load` 时卡住或误触发真实求解。
- 保证“检查 wiring”和“执行实验”两个动作分离，便于排错和复现。

### 反例

- 在 `__init__` 或 `build_solver()` 内直接调用 solver 的 `run()`。
- 在装配阶段进行大文件 IO 或全量评估计算。

### 推荐写法

```python
class MyProblem(BlackBoxProblem):
    def __init__(...):
        self._baseline = None

    def _ensure_baseline(self):
        if self._baseline is None:
            self._baseline = self._compute_baseline()
        return self._baseline

    def evaluate(self, x):
        baseline = self._ensure_baseline()
        ...
```

---

## 5. Core Contract Template (Required)

For every new adapter/pipeline/bias/plugin component, declare context contracts explicitly.

```python
class MyComponent:
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Explain the context interaction intent.",)
```

Notes:
- `context_requires/context_provides/context_mutates` are the core fields.
- If a field is not used, keep it as an empty tuple `()`.
- Avoid implicit context I/O in implementation without contract declaration.
