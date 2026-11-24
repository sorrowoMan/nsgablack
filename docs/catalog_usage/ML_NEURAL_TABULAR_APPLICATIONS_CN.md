# 神经表格：先用预设，再沿正式接缝改装

本页只核对源码与静态片段，没有运行训练、构造后端模型或下载依赖。所有例子使用 `mlblack/examples/cases/catalog_codec_demo` 的独立完整副本，保留 Project L0、默认 `linear_point` Case 和规范入口。预设实际组装模型、Problem、Provider 与优化 Adapter，不是一个 Bias。

## neural.tabular · MLP、TabNet 回归和分类的完整选择

**什么时候用：** 表格特征已是有限数值，需要明确选择模型族与任务；想知道配置最终由谁消费，而不是记一长串无用途的参数。

**先准备什么：** 当前三仓、NumPy、可用 CPU PyTorch（torch>=2.0）。8行训练、4行独立验证、2特征；分类标签0/1。这里不使用 sklearn TabNet 或预训练权重，TabNet 是框架自己的后端路由，不宣称复现外部论文的全部训练设定。三种模式使用同一数据划分。

**放在哪：** 完整替换 Case 的 config.py、pipeline/main.py、build_solver.py，新建 solver/neural.py；旧 adapter/problem 工厂不再由本 builder 调用，实际 Problem 由所选预设创建。Project 根新增本书末节的 run_neural_and_report.py。

**接入步骤：** 配置控制实际消费者，不根据文件名猜任务。

```python
# cases/linear_point/config.py
MODE = "mlp"
```

```python
# cases/linear_point/pipeline/main.py
import numpy as np
from mlblack.pipeline import NumericDataView

def build_pipeline(mode):
    rng = np.random.default_rng(17)
    X, V = rng.uniform(-1., 1., (8, 2)), rng.uniform(-1., 1., (4, 2))
    def labels(a):
        return ((a[:, 0] + a[:, 1] > 0.).astype(int) if mode == "tabnet_classification"
                else 1. + a[:, 0] - .5*a[:, 1])
    return NumericDataView(X_train=X, y_train=labels(X), X_valid=V, y_valid=labels(V),
        feature_names=("x0", "x1"))
```

```python
# cases/linear_point/solver/neural.py
from mlblack.presets import (build_mlp_regression_trainer,
    build_tabular_tabnet_regression_trainer, build_tabular_tabnet_classification_trainer)
from mlblack.integrations.nsgablack_gradient import build_gradient_trainer
from mlblack.representations import NeuralGraphRepresentation
from mlblack.problems import TabularNeuralRegressionProblem
from mlblack.core.artifacts import TorchModelArtifact

class PlainTorchArtifactProblem(TabularNeuralRegressionProblem):
    def build_model_artifact(self, model, context=None):
        return TorchModelArtifact(name="plain_torch_mlp", model=model,
            family="tabular", head="point", metadata={"task": "regression"})

def build_neural(data, mode, grant):
    if mode == "mlp":
        return build_mlp_regression_trainer(data, hidden_layers=(4,), activation="tanh",
            dropout=0., learning_rate=.01, batch_size=4, shuffle=False,
            optimizer="adamw", run_name="neural_mlp", resource_context=grant)
    if mode == "tabnet_regression":
        return build_tabular_tabnet_regression_trainer(data, hidden_dim=8,
            n_steps=2, relaxation_factor=1.5, ghost_bn=False, dropout=0., output_dim=1,
            compute_backend="torch", learning_rate=.01, random_seed=17,
            run_name="neural_tabnet_regression", resource_context=grant)
    if mode == "tabnet_classification":
        return build_tabular_tabnet_classification_trainer(data, hidden_dim=8,
            n_steps=2, relaxation_factor=1.5, ghost_bn=False, dropout=0., num_classes=2,
            compute_backend="torch", learning_rate=.01, random_seed=17,
            run_name="neural_tabnet_classification", resource_context=grant)
    if mode == "plain_torch_artifact":
        return build_gradient_trainer(problem=PlainTorchArtifactProblem(data),
            representation=NeuralGraphRepresentation.mlp(input_dim=2, hidden_layers=(4,),
                output_dim=1, activation="tanh", random_seed=17),
            method="gradient.adamw", compute_backend="torch", learning_rate=.01,
            resource_context=grant, run_name="plain_torch_artifact")
    raise ValueError("unknown neural mode")
```

MLP 预设内部固定表示/数据调度种子42，不接受 random_seed 参数；上面的17仅控制合成数据与 Solver，不能将两者混写。该预设实际绑定 NumericBatchSchedule，训练指标来自所选小批、验证指标用整个验证集。TabNet 预设不在此例另配数据调度，使用全部训练数据；ghost_bn=False 明确避免把小教学批误当大规模 Ghost BatchNorm。

实际路径为 NeuralGraphSpec → NeuralGraphRepresentation → **NeuralGraphCodec**，布局在 setup 中解析，init 后产生 UnknownState；编码器不拥有算法 Unit。TabNet Spec 的 classification/point Head 与输入维数由相应预设给出。预设中的 TabularNeuralRegressionProblem 或 TabularNeuralClassificationProblem 持有数据与损失；build_gradient_trainer 创建 **TorchEvaluationProvider**，由共享 Gateway 在 Project grant 内执行前向/微分，gradient.adamw Adapter 消费反馈/StateRef。不能把 Provider 单独当算法，不能把缓存 backend 当 L0 grant。

```python
# cases/linear_point/build_solver.py
from nsgablack.project import apply_solver_component_overrides
from .config import MODE
from .pipeline.main import build_pipeline
from .solver.neural import build_neural

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("edit this recipe's explicit config")
    solver = build_neural(build_pipeline(MODE), MODE, resource_context)
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(2)
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

默认 NeuralGraphArtifact 由对应 Problem 的 build_model_artifact 产生，包含图规格、布局、Head 和审计描述。它包着真实 Torch Module，正式 CaseRuntimeArtifactProvider 分离语义元数据和模型载荷，Torch state_dict 写 NPZ，成功 finalization 才发布 best_model_ref；TrainerResult 因而无需编码活 Module。不是把整个 Python 对象 pickle，也没有自动恢复 optimizer 的保证。

**怎样判断接对：** 本书结果入口保存 train/valid 指标、原始目标、Provider signals 和模型引用。回归单目标默认 valid.mse，分类默认 valid.log_loss，训练梯度仍来自训练集；不能把验证指标用作反向传播损失。classification 有 train/valid.accuracy，MLP batch 模式另看 provider.batch_size/batch_indices。2步只验证接线意图，不保证收敛，best_feedback 对应已评估 incumbent，而不是未送评的新参数。声明有 codec/Provider 或 Artifact 类型不能替代实际运行证据。

**运行入口：** 用末节两条正式命令，原默认组只执行这个 Case。依赖缺失、实际 Device 或能力不匹配应报错；不要静默把 TabNet 改为 NumPy MLP。

### 变体一：改为 TabNet 回归

**目的：** 保留连续任务，实际改为注意力掩码/特征变换模型。

**改在哪里：** 完整替换 config.py，工厂已有对应分支。

```python
MODE = "tabnet_regression"
```

**行为变化：** NeuralGraphSpec.tabular_tabnet 被预设实际创建，n_steps=2 是模型决策结构步数，不是 Solver generation。**限制：** hidden_dim/n_steps 改布局，不与 MLP checkpoint 混用；这里没有类别编码、缺值处理或论文级效果保证。

### 变体二：同族模型改为分类任务

**目的：** 同时改变标签规则、Head 和 Problem，避免只换模型名字。

**改在哪里：** 完整替换 config.py。

```python
MODE = "tabnet_classification"
```

**行为变化：** 数据变为0/1标签，Spec创建2类classification Head，Problem计算交叉熵。**限制：** 不支持把one-hot或任意字符串直接交给此工厂；真实类别映射须事先固定。

### 变体三：显式发布普通 TorchModelArtifact

**目的：** 给已有自定义 Torch Problem 一个最小正式模型发布入口。

**改在哪里：** 完整替换 config.py。

```python
MODE = "plain_torch_artifact"
```

**行为变化：** 实际装配 PlainTorchArtifactProblem，返回 TorchModelArtifact，经同一模型载荷/NPZ与引用链发布。**限制：** 此类型不额外保存 NeuralGraphArtifact 的专用图/布局审计字段；类型不同不表示文件天然可单独重建任意架构，使用者仍须保存匹配的结构定义。

源码：`mlblack/presets/neural.py`、`integrations/nsgablack_gradient.py`、`backends/torch_neural/evaluation_provider.py`、`problems/neural.py`、`representations/codecs/neural/base.py`、`core/artifacts.py`、`core/artifact_provider.py`。

## neural.tabular.run · 正式 Project 的结果读取

保存为副本根 `run_neural_and_report.py`。它只调用正式 execute_project 一次，不直接 fit 或创建训练循环。

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
    result = TrainerResult.from_dict(case.output)
    if result.best_feedback is None or result.best_model_ref is None:
        raise ValueError("evaluated feedback and published model required")
    payload = {"run_id": run.run_id, "objectives": result.best_objectives.tolist(),
        "metrics": dict(result.best_feedback.metrics), "signals": dict(result.best_feedback.signals),
        "model_ref": result.best_model_ref.as_dict()}
    path = root / "results" / "neural.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

副本根运行 `python run_project.py --check --build-check` 后，再运行 `python run_neural_and_report.py`。前者构造检查，后者真正训练；本轮均未执行。正式结果与 results/neural.json 的观察副本分开，新 run_id/成功 Case 状态才说明本次调用成功，旧文件不会因失败自动消失。
