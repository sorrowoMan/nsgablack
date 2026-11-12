# ML 异质输入：图像、图与偏好对的真实训练接线

三节分别使用现有正式 Project 的独立副本，示例数据均在本地合成。只完成静态源码、语法、来源与 seed 提取检查，未构造或训练模型、下载权重、调用 API 或执行运行命令。下列运行入口确实会训练小模型，不能把它描述为只读取数据的无副作用操作。

## mlblack.data_view.image · NCHW 图像分类与真实验证集

**什么时候用：** 一批图像要分类，而不是把像素表误当普通二维特征。本节同时演示 `mlblack.problem.tiny_cnn_image_classification`；输入是 NCHW，Problem 计算交叉熵，不用准确率冒充训练损失。

**先准备什么：** 当前 blackbase、nsgablack、mlblack、NumPy 和可用的 PyTorch（mlblack 的 `torch` 可选依赖，声明 torch>=2.0）。使用 `mlblack/examples/cases/benchmarks/` 副本中的 `cases/benchmark_tiny_cnn_classification/`。保留完整 Case、运行薄入口、Project L0，下面只改指定工厂并追加单 Case 组。使用 CPU，不需要 torchvision、预训练权重或在线模型；不会暗中下载图片。

**放在哪：** 本节路径相对 benchmarks Project。完整替换 Case 的 `pipeline/main.py`；原 `pipeline/__init__.py` 已导出 build_data，无需删改。完整替换规范 `build_solver.py`，原 build_trainer 别名保留。另增加一个只调用正式 Project 的结果报告薄入口。

**接入步骤：** `cases/benchmark_tiny_cnn_classification/pipeline/main.py`：

```python
import numpy as np
from mlblack.pipeline.data_views import ImageDataView

def build_data():
    X = np.zeros((6, 1, 4, 4), dtype=float)
    X[:3, 0, :2, :2] = 1.
    X[3:, 0, 2:, 2:] = 1.
    return ImageDataView(X_train=X,
        y_train=np.array([0, 0, 0, 1, 1, 1], dtype=int))
```

六张单通道 4×4 图，标签一维 `(6,)`，类别为 0/1。ImageDataView 检查四维和样本数，不能自动把 NHWC 转为 NCHW，也不做像素归一化。分类标签须为整数含义且在 `[0,num_classes)` 内；不能因为 DataView 接收数组就传 one-hot 或小数类别。

`cases/benchmark_tiny_cnn_classification/build_solver.py`：

```python
from mlblack.presets import build_tiny_cnn_image_classification_trainer
from nsgablack.core import BudgetController
from pipeline.main import build_data

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this recipe uses its declared components")
    trainer = build_tiny_cnn_image_classification_trainer(build_data(),
        conv_channels=(4,), num_classes=2, compute_backend="torch",
        learning_rate=1e-2, random_seed=51, run_name="structured_image",
        resource_context=resource_context)
    trainer.set_max_steps(2)
    trainer.register_controller(BudgetController(max_generations=2,
        name="structured_image.limit"))
    return trainer
```

保留原 builder 的 Case 导入约定：Project loader 在 Case 作用域解析 `pipeline.main`。公开 preset 实际创建 `NeuralGraphRepresentation.tiny_cnn`，由 NeuralGraphCodec 表达参数布局，分类 head 名为 `classification`、输出类别数为二；对应 TinyCNNImageClassificationProblem 持有 data。TorchEvaluationProvider 执行模型前向/自动微分，`gradient.adamw` Adapter 与 LearningSolver 共用 nsgablack 控制面，不另写 fit 循环。基础例没有验证集，原始单目标是 train 交叉熵；梯度来自训练损失。

在原 `project_config.py` 的 STAGES/GROUPS 定义后追加，保留 L0：

```python
STAGES.append(dict(name="structured_image", policy="serial",
    cases=["benchmark_tiny_cnn_classification"], resource_requests={
        "benchmark_tiny_cnn_classification": dict(threads=1, device="cpu", backend="local"),
    }))
GROUPS["structured_image"] = dict(stages=["structured_image"])
```

新增完整 Project 薄入口 `run_image_and_report.py`。它执行一次正式 Project，不直接调用模型，不再加训练循环：

```python
import json
from pathlib import Path
from blackbase.types import TrainerResult
from mlblack.project.project_runner import execute_project

def main():
    root = Path(__file__).resolve().parent
    run = execute_project(root, group="structured_image")
    case = next(c for c in run.case_results
                if c.request.case_name == "benchmark_tiny_cnn_classification")
    case.raise_for_failure()
    value = TrainerResult.from_dict(case.output)
    if value.best_feedback is None:
        raise ValueError("no evaluated model feedback")
    payload = dict(run_id=run.run_id, objectives=value.best_objectives.tolist(),
        metrics=dict(value.best_feedback.metrics), artifacts=list(value.artifact_refs),
        best_model_ref=None if value.best_model_ref is None else value.best_model_ref.as_dict())
    destination = root / "results" / "structured_image.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False,
        allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

**怎样判断接对：** 看本次 Project 收据及 `results/structured_image.json`。objectives 为一项；基础例对应 `metrics["train.log_loss"]`，另有 `train.accuracy/error_rate`。准确率在 `[0,1]`，不是必须达到某值。两次逻辑提交预算不等于两轮 epoch 或已保证收敛。结果属于 Solver 已评估的 incumbent，不拿未评估后继当最佳模型。正式结果可能通过 best_model_ref/report_ref 交付；上面从随结果保留的 best_feedback 读指标，不假定 report 永远 inline，也不重新训练来恢复模型。

**运行入口：** 在 mlblack 仓库根目录，副本则改路径：

```powershell
python examples/cases/benchmarks/run_project.py --group structured_image --check --build-check
python examples/cases/benchmarks/run_image_and_report.py
```

第一条只做装配检查；第二条才训练并写报告。不要再执行 default 组来“补报告”，原 default 还会启动其它三个训练 Case。本地 JSON 是观察副本，旧文件不证明新运行。

### 变体一：用独立噪声图检查验证损失

**目的：** 保留训练样本，另给带小背景扰动的同布局样本，观察验证指标；不再按训练损失挑 incumbent。

**改在哪里：** 完整替换同一 `pipeline/main.py`，其它代码不变：

```python
import numpy as np
from mlblack.pipeline.data_views import ImageDataView

def build_data():
    X = np.zeros((6, 1, 4, 4), dtype=float)
    X[:3, 0, :2, :2] = 1.
    X[3:, 0, 2:, 2:] = 1.
    V = np.zeros((4, 1, 4, 4), dtype=float)
    V[:2, 0, :2, :2] = 1.
    V[2:, 0, 2:, 2:] = 1.
    V += np.random.default_rng(91).normal(0., .03, V.shape)
    return ImageDataView(X_train=X, y_train=np.array([0, 0, 0, 1, 1, 1]),
        X_valid=V, y_valid=np.array([0, 0, 1, 1]))
```

**行为变化：** 原 Problem 默认 use_valid_objective=True，有验证集时目标变为 valid 交叉熵，报告新增 `valid.log_loss/accuracy/error_rate`；训练梯度仍来自训练集，不在验证集更新参数。

**限制：** train/valid 必须保持同一 C/H/W 与类别词表；这是合成扰动检查，不证明真实图像泛化。DataView 不替你划分数据或防止泄漏，验证集不能只是训练数组的别名。

源码：`mlblack/pipeline/data_views/image.py`、`presets/neural.py`、`problems/neural.py::TinyCNNImageClassificationProblem`、Torch `capabilities/losses.py`。

## mlblack.data_view.graph · 固定节点数的稠密图分类

**什么时候用：** 每个样本是一张小图，需要同时传节点特征和邻接矩阵。本节配套 `mlblack.problem.tiny_gnn_graph_classification`；这是图级分类，不是给每个节点一个标签。

**先准备什么：** 当前三仓、NumPy、PyTorch（torch>=2.0 可选依赖）。使用 `mlblack/examples/cases/benchmarks/` 独立副本的 `cases/benchmark_tiny_gnn_classification/`。保留完整 Case、Project L0、运行入口。此路由使用框架的 tiny GNN，不需要 PyG、图数据库、预训练图模型或网络下载。

**放在哪：** 路径相对 benchmarks Project。替换该 Case 的 `pipeline/main.py` 与 `build_solver.py`，保留现有 pipeline 包导出；在 Project 追加单 Case 组和下面结果报告薄入口。

**接入步骤：** `cases/benchmark_tiny_gnn_classification/pipeline/main.py`：

```python
import numpy as np
from mlblack.pipeline.data_views import GraphDataView

def build_data():
    X = np.zeros((6, 4, 3), dtype=float)
    A = np.repeat(np.eye(4)[None, :, :], 6, axis=0)
    for i in range(6):
        if i < 3:
            X[i, :, 0] = 1.
            A[i, 0, 1] = A[i, 1, 0] = 1.
        else:
            X[i, :, 1] = 1.
            A[i, 2, 3] = A[i, 3, 2] = 1.
    return GraphDataView(node_features_train=X, adjacency_train=A,
        y_train=np.array([0, 0, 0, 1, 1, 1], dtype=int))
```

X 是 `(样本数6,节点数4,每节点特征数3)`，A 是 `(6,4,4)`，y 是图级 `(6,)`。矩阵第 i 行/列与 X 的第 i 个节点必须对应。此例明确给对称边和自环，不靠 DataView 自动补边。DataView 检查数量和矩阵形状，不理解你的节点编号，也不自动把稀疏 edge_index、变长图列表或 padding mask 转为这个布局。

`cases/benchmark_tiny_gnn_classification/build_solver.py`：

```python
from mlblack.presets import build_tiny_gnn_graph_classification_trainer
from nsgablack.core import BudgetController
from pipeline.main import build_data

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this recipe uses its declared components")
    trainer = build_tiny_gnn_graph_classification_trainer(build_data(),
        hidden_dim=6, num_layers=2, num_classes=2, pooling="mean",
        compute_backend="torch", learning_rate=1e-2, random_seed=53,
        run_name="structured_graph", resource_context=resource_context)
    trainer.set_max_steps(2)
    trainer.register_controller(BudgetController(max_generations=2,
        name="structured_graph.limit"))
    return trainer
```

原 preset 从 DataView 的 node_feature_dim/num_nodes 建 tiny_gnn GraphSpec，NeuralGraphCodec 管理模型参数布局，分类 head 为 `classification`。TinyGNNGraphClassificationProblem 持有图数据并调用 `model(X,A)`，训练目标是交叉熵。TorchEvaluationProvider 做前向/自动微分，gradient.adamw/LearningSolver 走统一控制面；DataView 不拥有优化器，Codec 不是图数据解析器。

在原 `project_config.py` 定义后追加，保留 L0：

```python
STAGES.append(dict(name="structured_graph", policy="serial",
    cases=["benchmark_tiny_gnn_classification"], resource_requests={
        "benchmark_tiny_gnn_classification": dict(threads=1, device="cpu", backend="local"),
    }))
GROUPS["structured_graph"] = dict(stages=["structured_graph"])
```

新增完整 `run_graph_and_report.py`，只包装正式 Project：

```python
import json
from pathlib import Path
from blackbase.types import TrainerResult
from mlblack.project.project_runner import execute_project

def main():
    root = Path(__file__).resolve().parent
    run = execute_project(root, group="structured_graph")
    case = next(c for c in run.case_results
                if c.request.case_name == "benchmark_tiny_gnn_classification")
    case.raise_for_failure()
    value = TrainerResult.from_dict(case.output)
    if value.best_feedback is None:
        raise ValueError("no evaluated model feedback")
    payload = dict(run_id=run.run_id, objectives=value.best_objectives.tolist(),
        metrics=dict(value.best_feedback.metrics), artifacts=list(value.artifact_refs),
        best_model_ref=None if value.best_model_ref is None else value.best_model_ref.as_dict())
    destination = root / "results" / "structured_graph.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False,
        allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

**怎样判断接对：** 本次 `results/structured_graph.json` 应有单项目标，以及 `train.log_loss/accuracy/error_rate`；无验证集时目标对应 train.log_loss。检查新 run_id、Case 成功收据和 artifacts 引用；不预填准确率或宣称两步已训练好。best_feedback 属于已评估 incumbent，不能拿 Adapter 的待评估后继当结果。正式 report 可能是 report_ref；上面的读取不依赖 report inline，也不对模型重训来取指标。

**运行入口：** 从 mlblack 仓库根目录，副本则替换路径：

```powershell
python examples/cases/benchmarks/run_project.py --group structured_graph --check --build-check
python examples/cases/benchmarks/run_graph_and_report.py
```

检查不训练，报告入口才训练。不要运行原 default 来补摘要，它还会启动其它神经 Case。原 run_solver 的 runs/latest/summary.json 属于另一条 Case CLI 路径，不能假定 Project 一定生成它。

### 变体一：一致重编号，检查节点与邻接的对齐

**目的：** 数据导出时节点顺序变化，想检查特征与邻接是否一起重排，而不是只改 X 导致图语义错位。

**改在哪里：** 完整替换同一 `pipeline/main.py`，builder、报告和组不变：

```python
import numpy as np
from mlblack.pipeline.data_views import GraphDataView

def build_data():
    X = np.zeros((6, 4, 3), dtype=float)
    A = np.repeat(np.eye(4)[None, :, :], 6, axis=0)
    for i in range(6):
        if i < 3:
            X[i, :, 0] = 1.
            A[i, 0, 1] = A[i, 1, 0] = 1.
        else:
            X[i, :, 1] = 1.
            A[i, 2, 3] = A[i, 3, 2] = 1.
    y = np.array([0, 0, 0, 1, 1, 1])
    order = np.array([2, 0, 3, 1])
    return GraphDataView(node_features_train=X, adjacency_train=A, y_train=y,
        node_features_valid=X[:, order, :],
        adjacency_valid=A[:, order, :][:, :, order], y_valid=y.copy())
```

**行为变化：** 验证输入保留同一图的连接关系与图标签，原 Problem 默认把 valid 交叉熵作为单目标；梯度仍只用 train。报告新增 `valid.log_loss/accuracy/error_rate`。重排 A 的两个节点轴，而不是只改行或列。

**限制：** 这是相同图重编号的接线检查，验证集不独立，不能用它证明泛化或数学不变性。变长图须另找支持它的表示/Problem，不能把零填充节点当作此 DataView 已提供了掩码支持。

源码：`mlblack/pipeline/data_views/graph.py`、`presets/neural.py`、`problems/neural.py::TinyGNNGraphClassificationProblem`。

## mlblack.data_view.preference_pair · 成对 token 序列的 DPO 风格目标

**什么时候用：** 每行有一条 chosen 序列和一条 rejected 序列，希望提高前者相对概率。本节配套 `mlblack.problem.tiny_transformer_dpo_preference`；没有 y 分类标签，不把两个序列拼成普通数值回归特征。

**先准备什么：** 三仓、NumPy、PyTorch（torch>=2.0）。使用 `mlblack/examples/cases/tiny_transformer_smoke/` 独立副本的 `cases/tiny_transformer_preference/`。保留完整 Case、运行别名、Project L0。下面沿原 preset 改成 CPU tiny Transformer，从头初始化完整小模型；省略原 QLoRA 参数，不需要 transformers/PEFT/bitsandbytes，不下载预训练权重，不是给既有大模型做对齐。

**放在哪：** 路径相对 tiny_transformer_smoke Project。替换 Case `pipeline/main.py`、`build_solver.py`；pipeline 包原有 build_data 导出保留。原 Project default 会训练三个 Case，故追加一个只运行偏好 Case 的组与报告薄入口。

**接入步骤：** `cases/tiny_transformer_preference/pipeline/main.py`：

```python
import numpy as np
from mlblack.pipeline.data_views import PreferencePairDataView

def build_data():
    return PreferencePairDataView(
        chosen_train=np.array([[1, 2, 3, 4], [1, 3, 4, 5], [2, 3, 5, 6]], dtype=int),
        rejected_train=np.array([[1, 2, 2, 2], [1, 3, 3, 3], [2, 3, 3, 3]], dtype=int))
```

两矩阵均为 `(3,4)`，同一行构成一对。token 必须是整数含义且 `0<=id<10`；DataView 主要校验二维和同形，会转成浮点数组，Torch tensor capability 再转整数，不会替你发现小数 token 被截断。没有 tokenizer、自动 padding 或 prompt mask；此 Problem 按整条序列的 next-token 对数概率求和。长度至少二，本例固定四；model 实际输入前三 token，预测后三 token。

`cases/tiny_transformer_preference/build_solver.py`：

```python
from mlblack.presets import build_tiny_transformer_dpo_preference_trainer
from nsgablack.core import BudgetController
from pipeline.main import build_data

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this recipe uses its declared components")
    trainer = build_tiny_transformer_dpo_preference_trainer(build_data(),
        vocab_size=10, max_length=4, hidden_dim=8, num_layers=1, num_heads=2,
        beta=.1, compute_backend="torch", learning_rate=1e-2,
        random_seed=21, run_name="structured_preference", resource_context=resource_context)
    trainer.set_max_steps(1)
    trainer.register_controller(BudgetController(max_generations=1,
        name="structured_preference.limit"))
    return trainer
```

原 preset 建 NeuralGraphRepresentation.tiny_transformer、NeuralGraphCodec 与名为 `lm` 的 language_modeling head，位置长度为 max_length-1。对应 Problem 求 `-mean(logsigmoid(beta*(policy_margin-reference_margin)))`；policy_margin 为 chosen 与 rejected 的整序列 log probability 差。此 preset 没给 reference_model，参考 margin 为零，不能冒称比较了冻结预训练模型。TorchEvaluationProvider 负责前向/梯度，gradient.adamw 与 LearningSolver 共用原控制面；不是另一个私有 Trainer 循环。

在原 `project_config.py` 定义后追加，保留 L0：

```python
STAGES.append(dict(name="structured_preference", policy="serial",
    cases=["tiny_transformer_preference"], resource_requests={
        "tiny_transformer_preference": dict(threads=1, device="cpu", backend="local"),
    }))
GROUPS["structured_preference"] = dict(stages=["structured_preference"])
```

新增完整 Project 薄入口 `run_preference_and_report.py`：

```python
import json
from pathlib import Path
from blackbase.types import TrainerResult
from mlblack.project.project_runner import execute_project

def main():
    root = Path(__file__).resolve().parent
    run = execute_project(root, group="structured_preference")
    case = next(c for c in run.case_results
                if c.request.case_name == "tiny_transformer_preference")
    case.raise_for_failure()
    value = TrainerResult.from_dict(case.output)
    if value.best_feedback is None:
        raise ValueError("no evaluated model feedback")
    payload = dict(run_id=run.run_id, objectives=value.best_objectives.tolist(),
        metrics=dict(value.best_feedback.metrics), artifacts=list(value.artifact_refs),
        best_model_ref=None if value.best_model_ref is None else value.best_model_ref.as_dict())
    destination = root / "results" / "structured_preference.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False,
        allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

**怎样判断接对：** 本次 `results/structured_preference.json` 的 objectives 为一项，对应基础例 `train.dpo_loss`；另读 `train.preference_accuracy/policy_margin/reference_margin`。此例 reference_margin 应为零；preference_accuracy 比较每对 policy margin 是否大于参考 margin，并不是生成文本的质量评分。单步逻辑预算只演示路径，不宣称完成偏好训练。最佳反馈来自已评估 incumbent，不用优化器后继猜结果。报告只读取正式 TrainerResult 的反馈及引用，不重训取值。

**运行入口：** 在 mlblack 仓库根目录，副本则替换路径：

```powershell
python examples/cases/tiny_transformer_smoke/run_project.py --group structured_preference --check --build-check
python examples/cases/tiny_transformer_smoke/run_preference_and_report.py
```

前者检查、后者才训练；不再运行 default 组。保留本次 Project 收据和 run_id，本地 JSON 或旧 Case CLI summary 不替代本次正式发布证据。

### 变体一：将训练偏好与验证偏好分开

**目的：** 对未用于梯度更新的偏好对计算指标，并以验证 DPO loss 选择 incumbent。

**改在哪里：** 完整替换同一 `pipeline/main.py`，其余入口不变：

```python
import numpy as np
from mlblack.pipeline.data_views import PreferencePairDataView

def build_data():
    return PreferencePairDataView(
        chosen_train=np.array([[1, 2, 3, 4], [1, 3, 4, 5], [2, 3, 5, 6]]),
        rejected_train=np.array([[1, 2, 2, 2], [1, 3, 3, 3], [2, 3, 3, 3]]),
        chosen_valid=np.array([[1, 4, 5, 6], [2, 4, 6, 7]]),
        rejected_valid=np.array([[1, 4, 4, 4], [2, 4, 4, 4]]))
```

**行为变化：** train/valid 行数可以不同，各自 chosen/rejected 必须同形；本例 token 词表与长度四保持一致。默认 use_valid_objective=True 时，单目标改为 valid.dpo_loss，报告新增 valid 的四个同名指标；梯度仍来自训练对。

**限制：** 长度、词表或 tokenizer 变化要同步模型 GraphSpec，不能只改数组。没有 response mask，包含 prompt 的真实 DPO 数据不能直接声称只优化回答部分。无 reference 模型的这个目标也不等于完整大模型 DPO 流程；小合成样本不能证明泛化或对齐效果。

源码：`mlblack/pipeline/data_views/sequence.py`、`presets/neural.py`、`problems/neural.py::TinyTransformerDPOPreferenceProblem`、Torch `capabilities/losses.py::sequence_log_probs/dpo_loss_and_metrics`。
