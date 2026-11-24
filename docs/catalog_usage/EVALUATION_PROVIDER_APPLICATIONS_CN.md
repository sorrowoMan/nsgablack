# 评估 Provider：把评估方式接到正式 Case，而不偷换问题或偏好

每章独立使用，文件按标题落到对应标准 Case。以下 Project 改写未作为新实验执行；Provider 的 raw 反馈、Bias 单次投影、硬可行性门和计数边界另有针对性测试。`raw` 表示 Provider 交付给控制面的评估值；若 Provider 明确是 approximate，raw 不自动等于最高保真真值。

## plugin.surrogate_eval · 用真实数据暖启，再混合代理预测与真评估

**什么时候用：** 原 Problem 的目标很贵，接受在搜索过程中使用近似目标，并持续用少量真实调用纠正代理。它接管求值方式，不负责 DE 的供体、交叉或替换，也不是一个加分 Bias。

**先准备什么：** 使用现有 `examples/cases/assembled_parallel_cases/cases/de_bowl/`。保留 `problem/` 的二维 BowlProblem，目标为 `(x0-1)^2+(x1+2)^2`，边界 `[-4,4]`；保留 DE 工厂（12 名成员、12 行批次）、ClipRepair、配置和规范运行入口。需要 NumPy、scikit-learn 与当前框架。本例问题很便宜，只用来观察接线，不能据此宣称代理加速。

**放在哪：** 新增 `de_bowl/plugins/evaluation.py`，保留已有 `plugins/__init__.py`；builder 直接导入这个子模块，不依赖包里不存在的导出。以下文件含 Provider 工厂与只读报告，随后给完整 builder。

**接入步骤：**

```python
# cases/de_bowl/plugins/evaluation.py
import json
from pathlib import Path
from nsgablack.plugins import SurrogateEvaluationConfig, SurrogateEvaluationProviderPlugin
from nsgablack.plugins.base import Plugin


class ProviderReport(Plugin):
    def __init__(self, owner):
        super().__init__(name="surrogate_report")
        self.owner = owner

    def on_solver_finalized(self, result):
        control = self.solver
        feedback = control.get_last_feedback_batch()
        payload = {"run_id": control.run_session.run_id,
                   "dispatched_candidates": control.evaluation_count,
                   "problem_calls": control.problem.evaluation_count,
                   "provider_stats": dict(self.owner.stats),
                   "last_raw": feedback.raw_objectives.tolist(),
                   "last_selection": feedback.objectives.tolist(),
                   "last_fidelity": [item.info.get("evaluation_fidelity") for item in feedback.items]}
        output = Path(__file__).resolve().parents[1] / "results" / "surrogate.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def attach_evaluation(control):
    owner = SurrogateEvaluationProviderPlugin(
        config=SurrogateEvaluationConfig(min_train_samples=12, min_true_evals=2,
            topk_exploit=1, topk_explore=1, retrain_every_call=True, random_seed=17),
        model_type="rf")
    control.configure_evaluation_policy(allow_approximate=True)
    control.add_plugin(owner)
    control.add_plugin(ProviderReport(owner))
```

```python
# cases/de_bowl/build_solver.py：完整替换
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .adapter import build_adapter
from .pipeline import build_pipeline
from .problem import build_problem
from .plugins.evaluation import attach_evaluation


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    options = dict(config or {})
    control = ComposableSolver(build_problem(), adapter=build_adapter(),
        representation_pipeline=build_pipeline(), resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True)
    control.set_random_seed(int(options.get("seed", 17)))
    control.set_max_steps(int(options.get("max_steps", 6)))
    apply_solver_component_overrides(control, component_overrides)
    attach_evaluation(control)
    return control
```

能力查询只判断非空候选，不构造模型；第一次实际评估时才懒建 VectorSurrogate，并让整批进入暖启分支，而不是逐点重训。此时仍整批调用 Problem，再拟合一次。达到 min_train_samples 后才预测全体，再把预测最优、不确定性最高与最低真评估配额的并集重评。模型训练只收真实目标。Provider 返回原始约束和逐行 `evaluation_fidelity=true/surrogate`，不自己加 Bias；Solver 再统一投影一次，原始证据保留。`surrogate_std` 随 Feedback.metrics 传给偏好消费者，不塞整批对象进共享 context。

**怎样判断接对：** 查看该 Case 的 `results/surrogate.json`，核对本轮 run_id。provider_stats 的 true_evals/train_samples 是真实调用与训练行数，surrogate_calls 是预测批次数；dispatched_candidates 是控制面送评行数，两种成本不能混称。last_fidelity 明确哪些最后一批值是真值，哪些是预测；raw 并不抹掉 approximate 身份。仅打开 Catalog 不会拟合模型。本工厂没有声明可恢复代理缓存的状态 codec，不能把额外挂 checkpoint 称为模型续训已得到保证。

**运行入口：** 从 nsgablack 仓库根执行 `python examples/cases/assembled_parallel_cases/run_project.py`。现有默认组同时运行独立的 sa_valley；它不向这个 DE 交接候选。不要使用原 `run_and_report.py` 的固定步数假设来检查本章已改预算。也不要把本 Provider 与同优先级的另一批量 Provider 同时挂上：can_handle 是派发前承诺，选中后出错不会轮试下一个。显式提供 parallel_evaluator 时，其异常同样传播，不隐式把已开始的工作重跑串行。

### 变体一：接入一个已有的简化预测器，关闭在线训练

保留上方报告和 builder，只替换 `plugins/evaluation.py` 的 attach_evaluation，并在同文件定义下列预测器。这里用可直接读懂的解析近似演示接口，不伪装成已经训练的 RF。

```python
import numpy as np


class SimplifiedModel:
    def predict(self, x):
        x = np.asarray(x, dtype=float)
        return (0.8 * (x[:, 0] - 1.0) ** 2 + (x[:, 1] + 2.0) ** 2)[:, None]

    def uncertainty(self, x):
        return np.full((len(x), 1), 0.2)


def attach_evaluation(control):
    owner = SurrogateEvaluationProviderPlugin(surrogate=SimplifiedModel(), online_training=False,
        config=SurrogateEvaluationConfig(min_train_samples=0, min_true_evals=0,
            topk_exploit=0, topk_explore=0, retrain_every_call=False))
    control.configure_evaluation_policy(allow_approximate=True)
    control.add_plugin(owner)
    control.add_plugin(ProviderReport(owner))
```

本变体所有行都标 surrogate，Problem.evaluate 不应被此 Provider 调用，true_evals/train_samples 均为 0；约束仍由真实 Problem 计算。0.2 是演示的模型输出，不是经过校准的误差上界。没有真评估核验时，最终 incumbent 仍可能只是预测较好的候选，不能报告为已取得真实最优值。

## plugin.multi_fidelity_eval · 每批粗评全部，再精评一个明确子集

**什么时候用：** 已有同一问题的低成本近似与高成本版本，希望用粗评安排高保真机会，并清楚记录每个值来自哪一级。当前实现每批都粗评，不是达到某代后永久切换。

**先准备什么：** 独立使用 `assembled_parallel_cases/cases/de_bowl/`，保留原二维 Problem、12 行 DE 工厂与管线。本节低保真只保留第一坐标的代价，真实 Problem 还包含第二坐标；这故意不是等价函数，因此必须显式允许 approximate。不要与上一章同时启用两个 Provider。

**放在哪：** 新增或完整替换本 Case 的 `plugins/evaluation.py`，再完整替换 builder；两个文件如下。原规范入口和 Project L0 保留。

**接入步骤：**

```python
# cases/de_bowl/plugins/evaluation.py
import json
from pathlib import Path
from nsgablack.plugins import MultiFidelityEvaluationConfig, MultiFidelityEvaluationProviderPlugin
from nsgablack.plugins.base import Plugin


def coarse(candidate):
    return [(float(candidate[0]) - 1.0) ** 2]


class FidelityReport(Plugin):
    def __init__(self, owner):
        super().__init__(name="fidelity_report")
        self.owner = owner

    def on_solver_finalized(self, result):
        control = self.solver
        feedback = control.get_last_feedback_batch()
        payload = {"run_id": control.run_session.run_id,
                   "dispatched_candidates": control.evaluation_count,
                   "problem_calls": control.problem.evaluation_count,
                   "provider_stats": dict(self.owner.stats),
                   "last_raw": feedback.raw_objectives.tolist(),
                   "last_violations": feedback.raw_violations.tolist(),
                   "last_fidelity": [item.info["evaluation_fidelity"] for item in feedback.items]}
        output = Path(__file__).resolve().parents[1] / "results" / "fidelity.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def attach_evaluation(control):
    owner = MultiFidelityEvaluationProviderPlugin(low_fidelity=coarse,
        config=MultiFidelityEvaluationConfig(min_high_fidelity=3,
            topk_exploit=2, topk_explore=1, random_seed=17))
    control.configure_evaluation_policy(allow_approximate=True)
    control.add_plugin(owner)
    control.add_plugin(FidelityReport(owner))
```

```python
# cases/de_bowl/build_solver.py
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .adapter import build_adapter
from .pipeline import build_pipeline
from .problem import build_problem
from .plugins.evaluation import attach_evaluation


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    options = dict(config or {})
    control = ComposableSolver(build_problem(), adapter=build_adapter(),
        representation_pipeline=build_pipeline(), resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True)
    control.set_random_seed(int(options.get("seed", 17)))
    control.set_max_steps(int(options.get("max_steps", 6)))
    apply_solver_component_overrides(control, component_overrides)
    attach_evaluation(control)
    return control
```

低保真目标 shape 与 Problem 的目标数一致。topk_exploit 取粗评分数最小者；topk_explore 是无放回随机探索，不是按模型不确定性排序；二者去重并补到 min_high_fidelity。选中行被真实 Problem.evaluate 覆盖，其余保留低保真值。所有行的约束都由 Problem 求得，Bias 统一在返回后由控制面投影，不能把近似低违反量用作真实硬门。

**怎样判断接对：** 读取 `de_bowl/results/fidelity.json` 的当前 run_id，low_calls 应反映粗评行数，high_calls 与 problem_calls 反映实际高保真调用；它们不是同一个计数。last_fidelity 的 high/low 与 last_raw 按行对齐，不能把混合数组统称全真值。Solver 的 dispatched_candidates 仍只统计送评候选，而不是再加 low/high 内部调用。config 的 min_train_samples 当前没有训练消费者，不要用它推断模型暖启；当前没有 low_fidelity_ratio、switch_step 或 fallback_to_high_fidelity 这些配置。

**运行入口：** 从仓库根执行 `python examples/cases/assembled_parallel_cases/run_project.py`，默认还运行独立 sa_valley。框架默认禁止近似 Provider；若省略 allow_approximate，只会按默认规则走真实评估，不能据“搜索有结果”判断多保真已生效。注册后 can_handle 承诺交付；粗评函数异常会失败，不自动换另一 Provider 或伪造高保真结果。

### 变体一：每批全量高保真，用来核验近似策略的影响

只替换同文件 attach_evaluation；报告和 builder 不变。当前 DE 每批最多 12 行，补齐配额会被实际批次行数截断。

```python
def attach_evaluation(control):
    owner = MultiFidelityEvaluationProviderPlugin(low_fidelity=coarse,
        config=MultiFidelityEvaluationConfig(min_high_fidelity=12,
            topk_exploit=0, topk_explore=0, random_seed=17))
    control.configure_evaluation_policy(allow_approximate=True)
    control.add_plugin(owner)
    control.add_plugin(FidelityReport(owner))
```

这仍先粗评再高评，因此不节省粗评成本；应看到 last_fidelity 全部为 high，low_calls 与 high_calls 相等。只有这条配置在当前不超 12 行的宿主成立；换更大批次须重设配额。Provider 类型仍保守声明 approximate，不靠一次配置就改写语义标签。

## plugin.newton_solver · 在一次候选评估内求隐式状态

**什么时候用：** 外层候选是设计变量 x，但目标依赖内层方程解 y；希望替换数值后端而不把 y 当成外层 Adapter 的另一个搜索 Unit。本例方程为 `y²=x+1`，限定正根，外层原始目标为 `(y-1.5)²+0.02x`。

**先准备什么：** 在仓库根用正式 CLI 创建新 Project，安装当前框架、NumPy、SciPy。以下每个文件路径相对新 Project；保留生成的 Project L0、运行入口与包标记。

```powershell
python -m nsgablack project new examples/cases/newton_application
cd examples/cases/newton_application
python -m nsgablack project add-case search --type solver --framework nsgablack
```

**放在哪：** 分别保存下面五个文件。Problem 的两个隐式钩子必须成套提供；Provider 工厂放 plugins，SA 搜索逻辑仍放 adapter，builder 只接线。

**接入步骤：**

```python
# cases/search/problem/__init__.py
import numpy as np
from nsgablack.core import BlackBoxProblem


class ImplicitProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="positive_root_design", dimension=1,
                         bounds=[(0.0, 3.0)], objectives=["cost"])

    def evaluate(self, candidate):
        x = float(candidate[0])
        return [(np.sqrt(x + 1.0) - 1.5) ** 2 + 0.02 * x]

    def build_implicit_system(self, candidate, context):
        target = float(candidate[0]) + 1.0
        return {"residual": lambda y: np.array([y[0] ** 2 - target]),
                "jacobian": lambda y: np.array([[2.0 * y[0]]]),
                "x0": np.array([1.2])}

    def evaluate_from_implicit_solution(self, candidate, solution, context):
        x, y = float(candidate[0]), float(solution[0])
        if not np.isfinite(y) or y < 0 or abs(y * y - x - 1.0) > 1e-7:
            raise ValueError("implicit solution violates the positive-root contract")
        return [(y - 1.5) ** 2 + 0.02 * x]


def build_problem():
    return ImplicitProblem()
```

```python
# cases/search/pipeline/__init__.py
from nsgablack.representation import RepresentationPipeline, ClipRepair


def build_pipeline():
    return RepresentationPipeline(repair=ClipRepair(0.0, 3.0))
```

```python
# cases/search/adapter/__init__.py
from nsgablack.adapters import SimulatedAnnealingAdapter
from nsgablack.representation import UniformInitializer, GaussianMutation


def build_adapter():
    return SimulatedAnnealingAdapter(initializer=UniformInitializer(0.0, 3.0),
        mutator=GaussianMutation(sigma=0.15), batch_size=1, random_seed=17)
```

```python
# cases/search/plugins/evaluation.py
import json
from pathlib import Path
from nsgablack.plugins import NewtonSolverProviderPlugin, NumericalSolverConfig
from nsgablack.plugins.base import Plugin


class ImplicitReport(Plugin):
    def __init__(self, owner):
        super().__init__(name="implicit_report")
        self.owner = owner

    def on_solver_finalized(self, result):
        control = self.solver
        feedback = control.get_last_feedback_batch()
        payload = {"run_id": control.run_session.run_id,
                   "stats": dict(self.owner.stats),
                   "last_raw": feedback.raw_objectives.tolist(),
                   "last_metrics": [dict(item.metrics) for item in feedback.items]}
        output = Path(__file__).resolve().parents[1] / "results" / "implicit.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def attach_evaluation(control):
    owner = NewtonSolverProviderPlugin(config=NumericalSolverConfig(
        tol=1e-10, max_iter=100, fallback_to_problem_eval=False, warn_on_failure=False))
    control.add_plugin(owner)
    control.add_plugin(ImplicitReport(owner))
```

```python
# cases/search/build_solver.py
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .problem import build_problem
from .pipeline import build_pipeline
from .adapter import build_adapter
from .plugins.evaluation import attach_evaluation


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    control = ComposableSolver(build_problem(), adapter=build_adapter(),
        representation_pipeline=build_pipeline(), resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True)
    control.set_random_seed(17)
    control.set_max_steps(6)
    apply_solver_component_overrides(control, component_overrides)
    attach_evaluation(control)
    return control
```

Adapter 仍只提出 x；Provider 用 SciPy root(method="hybr") 求 y，Problem 转换钩子再给原始目标。Newton 当前只声明单点能力，批量由正式 individual_fallback 逐行调用，不必另写批量循环。控制面只投影一次 Bias，并保留 raw 目标与违反量。这里明确验残差和正根：后端 success=False 的统计标志本身不是领域验收，不能省掉转换钩子的正确性判断。

**怎样判断接对：** 查看 `cases/search/results/implicit.json`，按本轮 run_id 核对 stats.calls/success/failure/fallback、last_raw 与逐行 implicit_residual/implicit_iters/implicit_success。last_raw 是最后送评批次，不一定是 SA 当前点或最终 incumbent。Newton 的 last_iterations 来自 nfev，不能当成外层代数。报告是提交后的本地观察副本，不是独立权威 Artifact；方程解 y 也不会被自动写成外层候选。若 Provider 接受后返回 None 或抛错，仲裁器不会轮试 Broyden。

**运行入口：** 在新 Project 目录执行 `python run_project.py --check --build-check` 后，再执行 `python run_project.py`。本例没有运行或最优性收据；构造检查不能证明每个候选都能数值收敛。

### 变体一：把隐式状态限制接到真实硬可行性门

在同一 Problem 类新增两个方法，使直接评估与隐式评估保持同一约束。然后在 builder 的 ComposableSolver 构造中加入 `evaluation_acceptance_policy=FeasibleEvaluationAcceptance()`，并在同文件从 nsgablack.core 导入 FeasibleEvaluationAcceptance。

```python
def evaluate_constraints(self, candidate):
    return [float(np.sqrt(float(candidate[0]) + 1.0) - 1.6)]


def evaluate_constraints_from_implicit_solution(self, candidate, solution, context):
    return [float(solution[0]) - 1.6]
```

两个方法放在 ImplicitProblem 类内，不能作为顶层同名函数。硬门读取原始违反量，即使另挂 Bias 并软化选择违反量，也不能把 y>1.6 的候选放行。未接纳尝试不计逻辑代，仍消耗已发生求值；需要设置独立 max_step_attempts 时用 Solver 的正式入口，不把失败伪装成成功。

## plugin.broyden_solver · 保留同一隐式问题，改用无 Jacobian 后端

**什么时候用：** 目标仍依赖方程解，但没有可用 Jacobian，或希望比较另一种数值求解路线。Broyden 使用相同 Problem 钩子，忽略给出的 Jacobian；它不替代外层 SA 或 VNS。

**先准备什么：** 这是独立章节。创建新标准 Project，准备 NumPy、SciPy 与当前框架，保留生成的 L0、规范入口和包标记，不要求先执行 Newton 章。

```powershell
python -m nsgablack project new examples/cases/broyden_application
cd examples/cases/broyden_application
python -m nsgablack project add-case search --type solver --framework nsgablack
```

**放在哪：** 以下路径相对新 Project，完整提供 Problem、pipeline、adapter、Provider/报告和 builder。参数 x∈[0,3]，隐式正根满足 y²=x+1；原始目标为 `(y-1.5)²+0.02x`。

**接入步骤：**

```python
# cases/search/problem/__init__.py
import numpy as np
from nsgablack.core import BlackBoxProblem


class ImplicitProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="positive_root_design", dimension=1,
                         bounds=[(0.0, 3.0)], objectives=["cost"])

    def evaluate(self, candidate):
        x = float(candidate[0])
        return [(np.sqrt(x + 1.0) - 1.5) ** 2 + 0.02 * x]

    def build_implicit_system(self, candidate, context):
        target = float(candidate[0]) + 1.0
        return {"residual": lambda y: np.array([y[0] ** 2 - target]),
                "x0": np.array([1.2])}

    def evaluate_from_implicit_solution(self, candidate, solution, context):
        x, y = float(candidate[0]), float(solution[0])
        if not np.isfinite(y) or y < 0 or abs(y * y - x - 1.0) > 1e-7:
            raise ValueError("implicit solution violates the positive-root contract")
        return [(y - 1.5) ** 2 + 0.02 * x]


def build_problem():
    return ImplicitProblem()
```

```python
# cases/search/pipeline/__init__.py
from nsgablack.representation import RepresentationPipeline, ClipRepair


def build_pipeline():
    return RepresentationPipeline(repair=ClipRepair(0.0, 3.0))
```

```python
# cases/search/adapter/__init__.py
from nsgablack.adapters import SimulatedAnnealingAdapter
from nsgablack.representation import UniformInitializer, GaussianMutation


def build_adapter():
    return SimulatedAnnealingAdapter(initializer=UniformInitializer(0.0, 3.0),
        mutator=GaussianMutation(sigma=0.15), batch_size=1, random_seed=17)
```

```python
# cases/search/plugins/evaluation.py
import json
from pathlib import Path
from nsgablack.plugins import BroydenSolverProviderPlugin, NumericalSolverConfig
from nsgablack.plugins.base import Plugin


class ImplicitReport(Plugin):
    def __init__(self, owner):
        super().__init__(name="implicit_report")
        self.owner = owner

    def on_solver_finalized(self, result):
        control = self.solver
        feedback = control.get_last_feedback_batch()
        payload = {"run_id": control.run_session.run_id,
                   "stats": dict(self.owner.stats),
                   "last_raw": feedback.raw_objectives.tolist(),
                   "last_metrics": [dict(item.metrics) for item in feedback.items]}
        output = Path(__file__).resolve().parents[1] / "results" / "implicit.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def attach_evaluation(control):
    owner = BroydenSolverProviderPlugin(config=NumericalSolverConfig(
        tol=1e-8, max_iter=120, fallback_to_problem_eval=False, warn_on_failure=False))
    control.add_plugin(owner)
    control.add_plugin(ImplicitReport(owner))
```

```python
# cases/search/build_solver.py
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .problem import build_problem
from .pipeline import build_pipeline
from .adapter import build_adapter
from .plugins.evaluation import attach_evaluation


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    control = ComposableSolver(build_problem(), adapter=build_adapter(),
        representation_pipeline=build_pipeline(), resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True)
    control.set_random_seed(17)
    control.set_max_steps(6)
    apply_solver_component_overrides(control, component_overrides)
    attach_evaluation(control)
    return control
```

现实现使用 scipy.optimize.broyden1，max_iter 传给其 iter，tol 传给 f_tol；stats.last_iterations 来自 callback 次数，与 Newton 的 nfev 不是同一尺度。Provider 返回原始目标、原始违反量与 Feedback.metrics，Bias 由 Solver 统一处理。Problem 的转换钩子仍负责核对正根与领域残差；改变数值后端并不免除它。

**怎样判断接对：** 查看 `cases/search/results/implicit.json` 的当前 run_id、stats.calls/success/failure/fallback 与逐行 implicit_residual/implicit_iters/implicit_success。raw 目标按公式核对，但不要把最后一批当最终最佳；Solver incumbent 与 SA 接受的当前点也须分开。纯隐式路径不调用 Problem.evaluate，故其计数不能代表候选送评数；control.evaluation_count 记录控制面送评。原始约束可以由 evaluate_constraints_from_implicit_solution 提供，没有该钩子才使用 Problem.evaluate_constraints。

**运行入口：** 在新 Project 内先 `python run_project.py --check --build-check`，再 `python run_project.py`。本章节没有新运行收据。普通 batch 会沿正式逐点回退调用本 Provider；不把它挂上却期待 can_handle_population 直接返回 True。

### 变体一：仅在数值后端抛错时，显式启用同义问题回退

保留上方所有文件，只完整替换 plugins/evaluation.py 的 attach_evaluation。Problem.evaluate 已提供相同正根目标的解析实现，所以这个例子的回退具有清楚含义；实际业务没有同义备用计算时，不应照开。

```python
def attach_evaluation(control):
    owner = BroydenSolverProviderPlugin(config=NumericalSolverConfig(
        tol=1e-8, max_iter=120, fallback_to_problem_eval=True, warn_on_failure=True))
    control.add_plugin(owner)
    control.add_plugin(ImplicitReport(owner))
```

这是 Provider 内部显式的 exception 分支，stats.fallback 与 Problem.evaluation_count 才能确认是否发生；并不是仲裁器失败后尝试另一个 Provider。仅 result.success=False 并不会自动触发这个回退，仍须依靠领域转换校验拒绝不合格解；不允许把求解失败转换成任意软评分继续运行。回退同样返回原始约束，非零 Bias 也只应由控制面作用一次。
