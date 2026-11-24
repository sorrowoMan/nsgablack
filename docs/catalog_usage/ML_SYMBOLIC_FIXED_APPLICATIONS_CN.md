# 固定符号结构：参数、输出Head和基集合

本书各例使用 `mlblack/examples/cases/catalog_codec_demo/` 的独立完整副本；保留Project/L0/default单Case与规范入口。依赖当前三仓和NumPy，以下没有执行模型、数据计算或搜索，没有产生运行收据。固定表达式结构与外层符号结构搜索分开：本书Adapter只搜索表达式中的数值槽位。

## symbolic.fixed.host · 完整正式构造与结果读取

每例完整替换所示Case config/pipeline/main/problem；原pipeline包继续导出build_pipeline。将下列 `cases/linear_point/build_solver.py` 保存到每个独立副本，不调用旧adapter工厂：

```python
from mlblack.integrations.nsgablack_control import build_learning_solver
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter
from .pipeline.main import build_components
from .problem import build_problem

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this recipe uses explicit components")
    data, representation = build_components()
    solver = build_learning_solver(problem=build_problem(data), representation=representation,
        adapter=build_optimization_adapter("search.random_gaussian", population_size=8,
            mutation_scale=.2, objective_aggregation="sum"),
        resource_context=resource_context, compute_backend="numpy", run_name="fixed_symbolic")
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(8)
    return solver
```

Project根新增 `run_symbolic_and_report.py`：

```python
import json
from pathlib import Path
from blackbase.types import TrainerResult
from mlblack.project.project_runner import execute_project

def main():
    root = Path(__file__).resolve().parent
    run = execute_project(root)
    case = next(c for c in run.case_results if c.request.case_name == "linear_point")
    case.raise_for_failure()
    value = TrainerResult.from_dict(case.output)
    if value.best_feedback is None or value.best_model_ref is None:
        raise ValueError("expected evaluated feedback and symbolic Artifact")
    payload = {"run_id": run.run_id, "objectives": value.best_objectives.tolist(),
        "constraints": value.best_feedback.constraints.tolist(),
        "metrics": dict(value.best_feedback.metrics), "signals": dict(value.best_feedback.signals),
        "model_ref": value.best_model_ref.as_dict()}
    path = root / "results" / "symbolic.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

执行入口为副本根 `python run_project.py --check --build-check`，然后只执行一次 `python run_symbolic_and_report.py`。L0与发布仍由正式Project负责。Typed Artifact在Problem hook里明确携带JSON蓝图；ArtifactProvider提取model载荷并发布引用，typed describe进入引用metadata，不自动pickle活表达式模型。这里并未提供统一模型加载器，不能把蓝图类名当成已完成加载/恢复。

## mlblack.representation.symbolic_expression · 固定多项式，分别接点输出与区间输出

**什么时候用：** 你已决定函数形状 `b + w*x + q*x²`，只希望拟合系数；或把同一个符号Codec作为中心与半径的两块参数，输出预测区间。

**先准备什么：** 第一份Project副本及共用入口。32训练/12验证，一个输入特征，标签为带固定小噪声的二次函数。train是优化目标来源，valid只观察；本例不搜索“加一个sin”这种结构变化。

**放在哪：** 完整替换以下config、pipeline/main、problem文件；builder/report保存共用host节。旧其他Case工厂不再调用。

**接入步骤：** config.py：

```python
MODE = "point"
```

pipeline/main.py：

```python
import numpy as np
from mlblack.models import binary_expr, unary_expr, feature_expr, param_expr
from mlblack.pipeline import NumericDataView
from mlblack.representations import SymbolicExpressionConfig, SymbolicExpressionRepresentation
from mlblack.representations.heads import PointHead, CenterRadiusIntervalHead
from ..config import MODE

def build_pipeline():
    rng = np.random.default_rng(17)
    X, V = rng.uniform(-1., 1., (32, 1)), rng.uniform(-1., 1., (12, 1))
    def target(a):
        return 1.+2.*a[:, 0]-.5*a[:, 0]**2 + rng.normal(0., .05, len(a))
    return NumericDataView(X_train=X, y_train=target(X),
        X_valid=V, y_valid=target(V), feature_names=("x",))

def build_components():
    data = build_pipeline()
    x = feature_expr(0)
    expression = binary_expr("add", param_expr("b", init=0.),
        binary_expr("add", binary_expr("mul", param_expr("w", init=1.), x),
            binary_expr("mul", param_expr("q", init=.1), unary_expr("square", x))))
    if MODE == "point":
        head = PointHead()
    elif MODE == "interval":
        head = CenterRadiusIntervalHead(radius_transform="softplus")
    else:
        raise ValueError("unknown symbolic output")
    return data, SymbolicExpressionRepresentation(SymbolicExpressionConfig(
        input_dim=1, expression=expression, feature_names=("x",)), head=head)
```

SymbolicExpressionCodec从树中收集trainable参数，按**参数名字排序**，本例向量顺序为b/q/w，不能按树书写顺序猜b/w/q。同名参数共享槽位，同名但声明冲突会拒绝。PointHead维度3；CenterRadiusIntervalHead复制基础块，前3中心、后3raw radius，共6，softplus保证预测半径非负。Codec内部维度修整/非有限值兜底不是旧checkpoint兼容承诺，本例要求新运行且布局匹配。

problem/__init__.py：

```python
from mlblack.core.artifacts import SymbolicModelArtifact, SymbolicIntervalArtifact
from mlblack.problems import FixedSymbolicRegressionProblem, SupervisedIntervalRegressionProblem
from ..config import MODE

class PointProblem(FixedSymbolicRegressionProblem):
    def build_model_artifact(self, model, context):
        return SymbolicModelArtifact(name="polynomial_point", family="symbolic", head="point",
            model=model.describe(), representation={"parameter_order": list(model.parameter_names())})

class IntervalProblem(SupervisedIntervalRegressionProblem):
    def build_model_artifact(self, model, context):
        return SymbolicIntervalArtifact(name="polynomial_interval", family="symbolic", head="interval",
            model={"center": model.center_model.describe(), "radius": model.radius_model.describe(),
                   "radius_transform": model.radius_transform})

def build_problem(data):
    if MODE == "point":
        return PointProblem(data, use_valid_objective=False, complexity_weight=0., l2=0.)
    return IntervalProblem(data, use_valid_objective=False,
        target_coverage=.9, width_weight=1., miss_weight=10.)
```

Typed Artifact的model字段在此是完整表达式/参数蓝图，不是裸Python模型；保持安全可传输字典。不直接调用Artifact.save或虚构引用绕过最终发布。默认模型恢复可直接解码参数，本例未装额外fitter或内层Case，也未运行恢复验证。

**怎样判断接对：** point模式symbolic.json目标为[train.mse,0]，信号symbolic_expression是当前已评估表达式，symbolic.n_parameters为3；valid误差只观察。FixedSymbolicRegressionProblem实际计算训练参数梯度，但本例Gaussian不消费梯度；符号微分无规则时模型可能走数值差分，不能把has_gradient=True一概说成解析微分证明。复杂度正则和l2均为零，避免损失/目标口径混淆。

**运行入口：** 按共用正式Project命令读取本次结果与typed模型引用，8步不保证达到真实生成系数，更不证明发现了正确结构。

### 变体一：同一符号基础，输出预测区间

**目的：** 切换输出含义，避免把二列上下界塞进单点回归。

**改在哪里：** config.py完整替换为：

```python
MODE = "interval"
```

**行为变化：** 六参数中心/半径模型由区间Problem评估；目标为[width+10*miss,width,miss]，Gaussian与Solver都求和，即2*width+11*miss，并考虑正覆盖违反量。Artifact是SymbolicIntervalArtifact。**限制：** 它不是Normal概率分布或90%样本外保证；constraint=.9-train.coverage，验证仍只观察。旧3参数状态不能复用。区间Problem不提供该梯度，本例仍不装SGD。

## mlblack.representation.symbolic_basis_set · 两个符号列构成一个基集合

**什么时候用：** 希望表达式集合的输出是特征矩阵Z，而不是直接预测标签。需要检查列相关性、秩和条件数，随后再由明确的下游任务解释这些列。

**先准备什么：** 第二份Project副本与共用host。训练40/验证16，两列输入，其中x1与x0相关。NumericDataView要求y，所以下文提供零占位标签，但OrthogonalBasisEvaluationProblem不读取它；本例不做监督预测质量证明。

**放在哪：** 完整替换Case config.py、pipeline/main.py、problem/__init__.py。正式builder/report/L0仍用host。两个表达式各含一个trainable参数，因此维度为2，不能给完全无参数的表达式集合硬套数值搜索。

**接入步骤：** config.py：

```python
CONDITION_WEIGHT = .01
```

pipeline/main.py：

```python
import numpy as np
from mlblack.models import binary_expr, feature_expr, param_expr
from mlblack.pipeline import NumericDataView
from mlblack.representations import SymbolicBasisSetConfig, SymbolicBasisSetRepresentation
from mlblack.representations.heads import SymbolicBasisSetHead

def build_pipeline():
    rng = np.random.default_rng(17)
    def rows(n):
        u = rng.normal(size=n)
        return np.column_stack((u, .7*u + rng.normal(0., .3, n)))
    X, V = rows(40), rows(16)
    return NumericDataView(X_train=X, y_train=np.zeros(40), X_valid=V,
        y_valid=np.zeros(16), feature_names=("x0", "x1"))

def build_components():
    data = build_pipeline()
    genome = (
        {"name": "first", "expr": binary_expr("mul", param_expr("scale", init=1.), feature_expr(0))},
        {"name": "decorrelated", "expr": binary_expr("add", feature_expr(1),
            binary_expr("mul", param_expr("mix", init=0.), feature_expr(0)))},
    )
    return data, SymbolicBasisSetRepresentation(SymbolicBasisSetConfig(input_dim=2,
        genome=genome, feature_names=("x0", "x1")),
        head=SymbolicBasisSetHead(block_names=("first", "decorrelated"), block_dimensions=(1, 1)))
```

SymbolicMultiExpressionCodec按表达式块组织参数，Head用相同块名/维度解码为SymbolicBasisSetModel；model.transform(X)返回(n,2)，没有普通predict。这里的基不经QR/SVD自动正交化，参数mix改变第二列内容，scale影响条件数。

problem/__init__.py：

```python
from mlblack.core.artifacts import SymbolicModelArtifact
from mlblack.problems import OrthogonalBasisEvaluationProblem
from ..config import CONDITION_WEIGHT

class BasisProblem(OrthogonalBasisEvaluationProblem):
    def build_model_artifact(self, model, context):
        return SymbolicModelArtifact(name="two_symbolic_atoms", family="symbolic", head="basis_set",
            model={"atoms": [atom.describe() for atom in model.atoms]})

def build_problem(data):
    return BasisProblem(data, complexity_weight=0., condition_weight=CONDITION_WEIGHT)
```

**怎样判断接对：** symbolic.json三目标分别为basis.max_abs_corr、.01*basis.condition_number、0；还有basis.rank、n_atoms=2和表达式文字。全部基指标来自训练X，当前Problem不自动评估验证基或预测y；不要把零标签当监督成绩。相关矩阵对常数列有兜底，秩亏条件数可被替换为1e12，不能仅凭有限数或很小相关值宣布基满秩。最终按三目标和选择，不是Pareto档案。

**运行入口：** 用host正式Project入口；核对本轮模型引用保存两原子表达式参数。有限预算不保证完全消相关或满足任何正交定理。

### 变体一：去掉条件数权重，仅比较最大相关

**目的：** 观察这两个不同质量量如何影响基选择。

**改在哪里：** config.py完整替换为：

```python
CONDITION_WEIGHT = 0.
```

**行为变化：** 三目标中第二项变零，优化重心只剩最大相关，条件数指标仍报告。**限制：** 不能据相关值忽略秩亏/尺度失衡；不是删掉条件数计算。它也不自动给下游任务增加表达能力，未提供跨Case Artifact消费验收。

来源：mlblack/representations/symbolic.py、representations/codecs/symbolic.py、representations/heads/symbolic.py、models/symbolic.py、problems/symbolic.py、core/artifacts.py、core/artifact_provider.py。
