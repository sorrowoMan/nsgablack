# MLBlack数据、模型与装配组件逐项用法

本页逐项对应Catalog组件键。片段是组件级用法或正式Case中的装配片段；不是另一个训练runner。目录浏览不会执行它们。
代码根据当前实现核对，不能把source_checked理解为已完成训练验收。每节输入、装配位置、输出与依赖单独声明；模型Codec和Adapter Unit不是同一对象。

## mlblack.integration.learning_solver

**什么时候用：** 已有 ML 数据、模型表示和 LearningProblem，希望让优化 Adapter 搜索/更新模型参数，并复用共享预算、候选池、事务、检查点和结果发布。`LearningSolver` 提供 ML 的 fit 词汇，优化控制循环仍由 nsgablack.ComposableSolver 负责。

**先准备什么：** 在一个正式 Case 中准备四个工厂：数据工厂返回 NumericDataView，Problem 工厂消费该 DataView，Representation 根据列数声明模型维数，Adapter 工厂返回 nsgablack 的算法。下面复用 `catalog_codec_demo`：训练数据 `(24,2)`、目标 `(24,)`、默认 PointHead 的模型候选 `(3,)`；Case 的 `DEFAULTS` 提供 seed、n_samples、learning_rate、max_steps。`resource_context` 由外层 Project L0 传入，不在 Case 自行分配 GPU 或线程。

**放在哪：** 以下属于 mlblack 正式 `examples/cases/catalog_codec_demo/cases/linear_point/build_solver.py`。数据生成、问题目标和算法创建仍分别留在 `pipeline/`、`problem/`、`adapter/`；这里仅做规范装配。

**接入步骤：**

```python
from mlblack.integrations.nsgablack_control import build_learning_solver
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from nsgablack.project import apply_solver_component_overrides
from .adapter import build_adapter
from .config import DEFAULTS
from .pipeline import build_pipeline
from .problem import build_problem

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {**DEFAULTS, **dict(config or {})}
    data = build_pipeline(seed=settings["seed"], n_samples=settings["n_samples"])
    representation = LinearPointRepresentation(LinearPointConfig(
        n_features=data.n_features,
        feature_names=data.effective_feature_names,
        random_seed=int(settings["seed"]),
    ))
    solver = build_learning_solver(
        problem=build_problem(data), representation=representation,
        adapter=build_adapter(learning_rate=settings["learning_rate"]),
        resource_context=resource_context, run_name="catalog_linear_point",
    )
    solver.set_random_seed(int(settings["seed"]))
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

这里 `build_problem(data)` 返回 `SupervisedRegressionProblem(data, use_valid_objective=False)`；`build_adapter` 使用公开的 `build_optimization_adapter("gradient.sgd", learning_rate=...)`，没有私有训练循环。构造 Solver 后才由正式运行初始化候选与 Unit，装配函数本身不调用 `fit()`。

**运行入口：** 从 mlblack 仓库根目录使用 `python examples/cases/catalog_codec_demo/run_project.py --no-record`。该现有 Project 为唯一 Case 发放 1 个线程、0 GPU 的 CPU grant，默认最大提交步数为 3；这些是当前配置，不是本轮实测收据。

**怎样判断接对：** 正式 ML 结果用 `TrainerResult` 交付：`best_state` 是已评估的语义候选，`best_model` 或 `best_model_ref` 是与其绑定的模型，`best_objectives/best_feedback` 是对应反馈，另有 history、report 和 Artifact 引用。大对象可能只交付 DataRef，不能把空的内联字段直接判为失败。检查模型/反馈的候选身份、原始评价和生效资源；三个小步骤只用于接线核对，不能据此声称收敛。

**配套组件 key：** `mlblack.data_view.numeric`、`mlblack.problem.supervised_regression`、`mlblack.representation.linear_point`、`mlblack.codec.linear_point`、`mlblack.trainer.learning_solver`。

**接口依据与验证状态：** `mlblack.integrations.nsgablack_control:LearningSolver`、`build_learning_solver`、上述标准 Case 和 Project 配置；仅源码核对，未执行训练或调用模型服务。

## mlblack.trainer.learning_solver

**什么时候用：** 在 Catalog 按 trainer 语义寻找与 `integration.learning_solver` 相同的 ML 门面。两个键指向同一个 LearningSolver 类，不代表要同时构造两套控制器。

**先准备什么：** 按上一节完成同一 Case 的 DataView → Representation → LearningProblem → Adapter 装配。数值线性例子的特征矩阵为 `(n,2)`、模型状态为 `(3,)`；模型维数从 Representation 声明取得。Project 仍负责资源授权和 Case 执行。

**放在哪：** Case 的规范装配入口始终是 `build_solver.py`。如果外部工具需要 trainer 名称，在同目录 `build_trainer.py` 只放下面别名：

**接入步骤：**

```python
from .build_solver import build_solver as build_trainer
```

CLI 同理：`run_solver.py` 是规范入口，`run_trainer.py` 只转发它的 `main`。不要把数据处理、Adapter 构造或第二个 `for step` 循环复制到别名文件。需要程序式 fit 的调用方应在拿到同一 Case 装配结果后使用其 `fit()`；本用法仍以标准 Project 运行交付资源和结果。

**运行入口：** 从 mlblack 仓库根目录使用 `python examples/cases/catalog_codec_demo/run_project.py --no-record`。该 Project 会进入规范 Case，而不是执行 Catalog 中的代码块。

**怎样判断接对：** `build_trainer` 与 `build_solver` 导出同一工厂；运行只有一份 RunSession 进度、SolutionPool 与 ML 结果发布。`TrainerResult` 的字段和引用含义见上一节。浏览此条目或读取工厂签名不应构建运行 Unit，也不表示 fit 已完成。

**配套组件 key：** `mlblack.integration.learning_solver`、`mlblack.data_view.numeric`、`mlblack.representation.linear_point`、`mlblack.problem.supervised_regression`。

**接口依据与验证状态：** mlblack 的 `catalog/entries/trainer.toml`、`integrations/nsgablack_control.py`、`examples/cases/catalog_codec_demo/cases/linear_point/build_trainer.py`；仅源码核对。

## mlblack.data_view.numeric

**什么时候用：** 做数值特征上的监督学习，准备把训练/验证数据交给 LearningProblem。它保存数据布局和样本含义，不选择算法、不拟合模型。

**先准备什么：** `X_train` 必须是 `(n_train,p)` 二维数值矩阵，`y_train` 是 `(n_train,)` 一维目标；验证集若有，`X_valid/y_valid` 必须成对提供且行数匹配。`feature_names` 恰好有 `p` 个，列顺序同时决定模型权重顺序。以下数据只由固定种子的公开公式生成，`seed` 与 `n_samples` 是 Case 配置实参。

**放在哪：** 正式 `catalog_codec_demo/cases/linear_point/pipeline/main.py::build_pipeline`。此 ML Case 的 pipeline 工厂返回的是 DataView；`build_solver.py` 把它传给 `problem/build_problem(data)`，不要直接传给 Adapter。

**接入步骤：**

```python
import numpy as np
from mlblack.pipeline.data_views import NumericDataView

def build_pipeline(*, seed=17, n_samples=24):
    rng = np.random.default_rng(int(seed))
    X = rng.uniform(-1.0, 1.0, size=(int(n_samples), 2))
    y = 1.0 + 2.0 * X[:, 0] - 0.5 * X[:, 1]
    return NumericDataView(X_train=X, y_train=y,
                           feature_names=("x0", "x1"))
```

在 `build_solver.py` 先执行数据工厂，再用 `data.n_features` 配置 Representation，用 `SupervisedRegressionProblem(data, use_valid_objective=False)` 定义原始回归目标。本例没有验证集，所以显式关闭验证集目标；使用自己的数据时应先决定拆分规则，再构造 DataView。

**运行入口：** 从 mlblack 仓库根目录运行 `python examples/cases/catalog_codec_demo/run_project.py --no-record`。这是现有标准 Project，含 CPU 资源声明和一个 `linear_point` Case；本轮未运行。

**怎样判断接对：** 默认 `data.describe()` 的布局应是 `n_train=24`、`n_valid=0`、`n_features=2`、特征名 `("x0","x1")`，并且 Problem 与 Representation 都消费同一个列顺序。这里是布局结果，不是训练分数；看到数据描述不能标为模型训练完成。

**配套组件 key：** `mlblack.problem.supervised_regression`、`mlblack.representation.linear_point`、`mlblack.codec.linear_point`、`mlblack.integration.learning_solver`。

**接口依据与验证状态：** `mlblack/pipeline/data_views/numeric.py`、`examples/cases/catalog_codec_demo/cases/linear_point/`（路径相对 mlblack 仓库）；源码核对，未创建数据文件或启动训练。

## mlblack.data_view.time_series

Ordered univariate time-series data with optional exogenous features.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
print(series.describe())
```

**预期输出：** 60个按时间顺序的观测；这里没有随机切分或泄漏未来值。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.data_views.time_series:TimeSeriesDataView`

## mlblack.data_view.image

Image tensors in NCHW layout.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.image import ImageDataView
view = ImageDataView(X_train=np.zeros((4, 1, 8, 8)), y_train=np.array([0, 1, 0, 1]))
print(view.describe())
```

**预期输出：** 4张单通道8×8图像及4个标签；形状由图像DataView检查。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.data_views.image:ImageDataView`

## mlblack.data_view.graph

Dense graph tensors for small GNN smoke tasks.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.graph import GraphDataView
view = GraphDataView(node_features_train=np.zeros((4, 3, 2)),
    adjacency_train=np.tile(np.eye(3), (4, 1, 1)), y_train=np.array([0, 1, 0, 1]))
print(view.describe())
```

**预期输出：** 4个图、每图3节点、每节点2特征，邻接矩阵与标签行对齐。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.data_views.graph:GraphDataView`

## mlblack.data_view.image_contrastive_pair

Anchor/positive/negative image triples for retrieval smoke tasks.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.contrastive import ImageContrastivePairDataView
view = ImageContrastivePairDataView(anchor_train=np.zeros((3, 1, 8, 8)),
    positive_train=np.ones((3, 1, 8, 8)), negative_train=np.full((3, 1, 8, 8), 2.))
print(view.describe())
```

**预期输出：** anchor/positive/negative按三元组对齐；没有伪造监督标签。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.data_views.contrastive:ImageContrastivePairDataView`

## mlblack.data_view.preference_pair

Token-id pairs for preference/DPO-style training.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.sequence import PreferencePairDataView
view = PreferencePairDataView(chosen_train=np.array([[1,2,0], [2,3,0]]),
    rejected_train=np.array([[1,4,0], [2,4,0]]))
print(view.describe())
```

**预期输出：** 两对同形的chosen/rejected序列；用于偏好任务，不等于普通分类y。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.data_views.sequence:PreferencePairDataView`

## mlblack.head.point

Point-output head: one base model, direct predict output.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.representations.heads.point import PointHead
from mlblack.representations.codecs.linear import LinearPointCodec, LinearCodecConfig
codec = LinearPointCodec(LinearCodecConfig(n_features=2))
head = PointHead()
values = np.zeros(head.parameter_size(codec.base_dimension))
model = head.decode(values, base_dimension=codec.base_dimension, base_decode=codec.decode)
print(model.predict(X))
```

**预期输出：** 输出与4个输入样本逐行对齐；Head决定点、概率、区间或分布语义，Codec只负责参数布局。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.heads.point:PointHead`

## mlblack.head.binary_logistic

Wraps a scalar logit decoder as binary predict_proba output.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.representations.heads.probability import BinaryLogisticHead
from mlblack.representations.codecs.linear import LinearPointCodec, LinearCodecConfig
codec = LinearPointCodec(LinearCodecConfig(n_features=2))
head = BinaryLogisticHead(threshold=0.5)
values = np.zeros(head.parameter_size(codec.base_dimension))
model = head.decode(values, base_dimension=codec.base_dimension, base_decode=codec.decode)
print(model.predict_proba(X))
```

**预期输出：** 输出与4个输入样本逐行对齐；Head决定点、概率、区间或分布语义，Codec只负责参数布局。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.heads.probability:BinaryLogisticHead`

## mlblack.head.softmax

Allocates one base decoder block per class and returns softmax probabilities.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.representations.heads.probability import SoftmaxHead
from mlblack.representations.codecs.linear import LinearPointCodec, LinearCodecConfig
codec = LinearPointCodec(LinearCodecConfig(n_features=2))
head = SoftmaxHead(n_classes=3)
values = np.zeros(head.parameter_size(codec.base_dimension))
model = head.decode(values, base_dimension=codec.base_dimension, base_decode=codec.decode)
print(model.predict_proba(X))
```

**预期输出：** 输出与4个输入样本逐行对齐；Head决定点、概率、区间或分布语义，Codec只负责参数布局。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.heads.probability:SoftmaxHead`

## mlblack.head.probability_calibration

Base probability/logit model plus one temperature parameter.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.representations.heads.probability import ProbabilityCalibrationHead
from mlblack.representations.codecs.linear import LinearPointCodec, LinearCodecConfig
codec = LinearPointCodec(LinearCodecConfig(n_features=2))
head = ProbabilityCalibrationHead()
values = np.zeros(head.parameter_size(codec.base_dimension))
model = head.decode(values, base_dimension=codec.base_dimension, base_decode=codec.decode)
print(model.predict_proba(X))
```

**预期输出：** 输出与4个输入样本逐行对齐；Head决定点、概率、区间或分布语义，Codec只负责参数布局。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.heads.probability:ProbabilityCalibrationHead`

## mlblack.head.center_radius_interval

Interval head: center base model + positive radius base model.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.representations.heads.interval import CenterRadiusIntervalHead
from mlblack.representations.codecs.linear import LinearPointCodec, LinearCodecConfig
codec = LinearPointCodec(LinearCodecConfig(n_features=2))
head = CenterRadiusIntervalHead()
values = np.zeros(head.parameter_size(codec.base_dimension))
model = head.decode(values, base_dimension=codec.base_dimension, base_decode=codec.decode)
print(model.predict_interval(X))
```

**预期输出：** 输出与4个输入样本逐行对齐；Head决定点、概率、区间或分布语义，Codec只负责参数布局。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.heads.interval:CenterRadiusIntervalHead`

## mlblack.head.two_model_interval / mlblack.head.interval

Interval head: lower base model + upper base model.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.representations.heads.interval import TwoModelIntervalHead
from mlblack.representations.codecs.linear import LinearPointCodec, LinearCodecConfig
codec = LinearPointCodec(LinearCodecConfig(n_features=2))
head = TwoModelIntervalHead()
values = np.zeros(head.parameter_size(codec.base_dimension))
model = head.decode(values, base_dimension=codec.base_dimension, base_decode=codec.decode)
print(model.predict_interval(X))
```

**预期输出：** 输出与4个输入样本逐行对齐；Head决定点、概率、区间或分布语义，Codec只负责参数布局。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.heads.interval:TwoModelIntervalHead`, `mlblack.representations.heads.interval:IntervalHead`

## mlblack.head.normal

NormalHead(sigma_transform: 'str' = 'softplus')

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.representations.heads.distribution import NormalHead
from mlblack.representations.codecs.linear import LinearPointCodec, LinearCodecConfig
codec = LinearPointCodec(LinearCodecConfig(n_features=2))
head = NormalHead()
values = np.zeros(head.parameter_size(codec.base_dimension))
model = head.decode(values, base_dimension=codec.base_dimension, base_decode=codec.decode)
print(model.predict_params(X))
```

**预期输出：** 输出与4个输入样本逐行对齐；Head决定点、概率、区间或分布语义，Codec只负责参数布局。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.heads.distribution:NormalHead`

## mlblack.head.poisson

PoissonHead(rate_transform: 'str' = 'softplus')

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.representations.heads.distribution import PoissonHead
from mlblack.representations.codecs.linear import LinearPointCodec, LinearCodecConfig
codec = LinearPointCodec(LinearCodecConfig(n_features=2))
head = PoissonHead()
values = np.zeros(head.parameter_size(codec.base_dimension))
model = head.decode(values, base_dimension=codec.base_dimension, base_decode=codec.decode)
print(model.predict_params(X))
```

**预期输出：** 输出与4个输入样本逐行对齐；Head决定点、概率、区间或分布语义，Codec只负责参数布局。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.heads.distribution:PoissonHead`

## mlblack.head.negative_binomial

NegativeBinomialHead(alpha_transform: 'str' = 'softplus')

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.representations.heads.distribution import NegativeBinomialHead
from mlblack.representations.codecs.linear import LinearPointCodec, LinearCodecConfig
codec = LinearPointCodec(LinearCodecConfig(n_features=2))
head = NegativeBinomialHead()
values = np.zeros(head.parameter_size(codec.base_dimension))
model = head.decode(values, base_dimension=codec.base_dimension, base_decode=codec.decode)
print(model.predict_params(X))
```

**预期输出：** 输出与4个输入样本逐行对齐；Head决定点、概率、区间或分布语义，Codec只负责参数布局。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.heads.distribution:NegativeBinomialHead`

## mlblack.head.piecewise

Allocates one base decoder block per branch and returns a PiecewiseModel.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.representations.heads.conditional import PiecewiseHead
from mlblack.representations.codecs.linear import LinearPointCodec, LinearCodecConfig
codec = LinearPointCodec(LinearCodecConfig(n_features=2))
head = PiecewiseHead(n_branches=2)
values = np.zeros(head.parameter_size(codec.base_dimension))
model = head.decode(values, base_dimension=codec.base_dimension, base_decode=codec.decode)
print(model.predict(X))
```

**预期输出：** 输出与4个输入样本逐行对齐；Head决定点、概率、区间或分布语义，Codec只负责参数布局。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.heads.conditional:PiecewiseHead`

## mlblack.head.symbolic_basis_set

Multi-symbol head that splits one state into expression blocks.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.representations.heads.symbolic import SymbolicBasisSetHead
from mlblack.representations.codecs.symbolic import SymbolicMultiExpressionCodec, SymbolicMultiExpressionCodecConfig
codec = SymbolicMultiExpressionCodec(SymbolicMultiExpressionCodecConfig(input_dim=1, genome=({'type': 'binary', 'op': 'mul', 'left': {'type': 'param', 'name': 'slope', 'init': 2.0}, 'right': {'type': 'feature', 'index': 0}},)))
head = SymbolicBasisSetHead(block_names=('slope',), block_dimensions=codec.block_dimensions)
model = head.decode(codec.init_values(), base_dimension=codec.total_dimension,
    base_decode=lambda values, context: codec.decode_term(context['symbolic.expression_index'], values, context))
print(model.transform(np.array([[1.], [2.]])))
```

**预期输出：** 两个样本的一列符号基函数值；Head按表达式块路由，不能用线性模型冒充SymbolicExpressionModel。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.heads.symbolic:SymbolicBasisSetHead`

## mlblack.codec.linear_point

**什么时候用：** 想明确线性模型每一维参数的意义，或需要把已有 `LinearPointModel` 编码为参数向量。完整搜索训练通常直接装配 `LinearPointRepresentation`，它内部已经使用本 Codec。

**先准备什么：** `n_features=p` 来自 DataView 的列数，参数布局固定为 `[intercept,w0,...,w(p-1)]`，shape 为 `(p+1,)`。预测矩阵为 `(n,p)`。下面 `X` 和参数均在片段内给出，没有隐藏的训练数据、已拟合对象或 Adapter 状态。

**放在哪：** Case `pipeline/` 的模型表示模块，或离线导入/导出模型的语义组件函数；不要放进 Adapter Unit builder。正式 `catalog_codec_demo` 通过 `LinearPointRepresentation.codec` 使用它。

**接入步骤：**

```python
import numpy as np
from mlblack.representations.codecs.linear import LinearPointCodec, LinearCodecConfig

def inspect_linear_layout():
    codec = LinearPointCodec(LinearCodecConfig(
        n_features=2, feature_names=("x0", "x1")))
    parameters = np.array([1.0, 2.0, -0.5])
    model = codec.decode(parameters)
    X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
    return model.predict(X), codec.encode(model), codec.parameter_layout()
```

`decode` 按给定参数构造模型，不会拟合。要进入训练生命周期，在 `build_solver.py` 装配 `LinearPointRepresentation(LinearPointConfig(n_features=data.n_features, ...))`，由 LearningSolver 产生候选；不要先调用 Codec.init_values 生成一批无运行身份的训练种群。

**运行入口：** 从 mlblack 仓库根目录使用 `python examples/cases/catalog_codec_demo/run_project.py --no-record`。标准 Case 实际使用原始线性 Codec 与 PointHead；它没有装配正交特征 Codec 或神经网络。

**怎样判断接对：** 按线性公式，上述确定参数的预测应为 `[0.5,3.0,4.5,7.0]`，encode 应返回 `[1.0,2.0,-0.5]`，layout 的总长度为 3。这是接口的确定含义，本轮没有执行片段。训练结果还须看正式结果中的已评估 best_state/best_feedback，不能把 decode 成功当作拟合成功。

**配套组件 key：** `mlblack.data_view.numeric`、`mlblack.representation.linear_point`、`mlblack.head.point`、`mlblack.model.linear_point`、`mlblack.integration.learning_solver`。

**接口依据与验证状态：** `mlblack.representations.codecs.linear:LinearPointCodec` 与 mlblack 的 `catalog_codec_demo` 正式 Case；仅源码核对。

## mlblack.codec.orthogonal_linear_point

Orthogonal-feature linear parameter codec.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.representations.codecs.linear import OrthogonalLinearPointCodec
codec = OrthogonalLinearPointCodec.from_data(X)
model = codec.decode(codec.init_values())
print(model.predict(X))
print(codec.describe())
```

**预期输出：** 在训练X上建立正交特征映射，再按映射维数解释参数；后续预测复用该映射。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.codecs.linear:OrthogonalLinearPointCodec`

## mlblack.codec.tunable_parameter

TunableParameterSpec(name: 'str', low: 'float' = 0.0, high: 'float' = 1.0, integer: 'bool' = False)

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.representations.codecs.estimators import TunableParameterSpec
depth = TunableParameterSpec(name='max_depth', low=2, high=8, integer=True)
print(depth.repair(10.3))
print(depth.as_dict())
```

**预期输出：** max_depth被修复到整数上界8；该对象描述超参数，不能直接当作拟合模型。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.codecs.estimators:TunableParameterSpec`

## mlblack.codec.estimator_spec

External estimator-spec codec with typed mechanism metadata.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from sklearn.tree import DecisionTreeRegressor
from mlblack.representations.codecs.estimators import EstimatorSpecCodec, EstimatorCodecConfig, TunableParameterSpec
codec = EstimatorSpecCodec(EstimatorCodecConfig(family='tree', route='sklearn.tree.DecisionTreeRegressor',
    tunables=(TunableParameterSpec('max_depth', 2, 8, integer=True),),
    factory=lambda parameters: DecisionTreeRegressor(**parameters)))
spec_model = codec.decode(codec.init_values())
print(spec_model.describe())
print(type(spec_model.build_estimator()).__name__)
```

**预期输出：** 得到参数Spec并经显式factory创建估计器；route字符串只是标识，不会自动导入或fit，实际拟合交给Problem/Provider。

**依赖与边界：** NumPy、scikit-learn；显式factory只创建估计器，不在Codec里训练。

**接口依据：** `mlblack.representations.codecs.estimators:EstimatorSpecCodec`

## mlblack.codec.neural_temporal_deepar_spec

构建 DeepAR 风格概率预测的 NeuralGraphSpec 路由，LSTM 主干输出 mu 和 log_sigma 分布参数。

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.representations.codecs.neural.specs import NeuralGraphSpec
from mlblack.representations.codecs.neural.base import NeuralGraphCodec
spec = NeuralGraphSpec.temporal_deepar(input_dim=1, sequence_length=12)
codec = NeuralGraphCodec(spec)
print(spec.as_dict())
print(codec.describe())
```

**预期输出：** 构造本条目对应网络结构与未解析backend描述；精确布局须由正式Trainer/L0后端上下文解析，没有在组件内自行开启后端。

**依赖与边界：** NumPy与统一环境；实际parameter_layout(context=...)与网络求值另需正式ML调用提供支持该架构的backend.session。

**接口依据：** `mlblack.representations.codecs.neural.specs:NeuralGraphSpec.temporal_deepar`

## mlblack.codec.neural_temporal_lstm_spec

构建 LSTM 风格序列预测的 NeuralGraphSpec 路由，通过后端神经网络降层执行。

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.representations.codecs.neural.specs import NeuralGraphSpec
from mlblack.representations.codecs.neural.base import NeuralGraphCodec
spec = NeuralGraphSpec.temporal_lstm(input_dim=1, sequence_length=12)
codec = NeuralGraphCodec(spec)
print(spec.as_dict())
print(codec.describe())
```

**预期输出：** 构造本条目对应网络结构与未解析backend描述；精确布局须由正式Trainer/L0后端上下文解析，没有在组件内自行开启后端。

**依赖与边界：** NumPy与统一环境；实际parameter_layout(context=...)与网络求值另需正式ML调用提供支持该架构的backend.session。

**接口依据：** `mlblack.representations.codecs.neural.specs:NeuralGraphSpec.temporal_lstm`

## mlblack.codec.neural_temporal_nbeats_spec

构建 N-BEATS 风格堆叠残差块预测的 NeuralGraphSpec 路由，通过后端神经网络降层执行。

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.representations.codecs.neural.specs import NeuralGraphSpec
from mlblack.representations.codecs.neural.base import NeuralGraphCodec
spec = NeuralGraphSpec.temporal_nbeats(input_dim=1, sequence_length=12)
codec = NeuralGraphCodec(spec)
print(spec.as_dict())
print(codec.describe())
```

**预期输出：** 构造本条目对应网络结构与未解析backend描述；精确布局须由正式Trainer/L0后端上下文解析，没有在组件内自行开启后端。

**依赖与边界：** NumPy与统一环境；实际parameter_layout(context=...)与网络求值另需正式ML调用提供支持该架构的backend.session。

**接口依据：** `mlblack.representations.codecs.neural.specs:NeuralGraphSpec.temporal_nbeats`

## mlblack.codec.neural_temporal_patchtst_spec

构建 PatchTST 风格补丁嵌入 + Transformer 编码器预测的 NeuralGraphSpec 路由。

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.representations.codecs.neural.specs import NeuralGraphSpec
from mlblack.representations.codecs.neural.base import NeuralGraphCodec
spec = NeuralGraphSpec.temporal_patchtst(input_dim=1, sequence_length=12)
codec = NeuralGraphCodec(spec)
print(spec.as_dict())
print(codec.describe())
```

**预期输出：** 构造本条目对应网络结构与未解析backend描述；精确布局须由正式Trainer/L0后端上下文解析，没有在组件内自行开启后端。

**依赖与边界：** NumPy与统一环境；实际parameter_layout(context=...)与网络求值另需正式ML调用提供支持该架构的backend.session。

**接口依据：** `mlblack.representations.codecs.neural.specs:NeuralGraphSpec.temporal_patchtst`

## mlblack.codec.neural_temporal_tcn_spec

构建 TCN 风格序列预测的 NeuralGraphSpec 路由，通过后端神经网络降层执行。

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.representations.codecs.neural.specs import NeuralGraphSpec
from mlblack.representations.codecs.neural.base import NeuralGraphCodec
spec = NeuralGraphSpec.temporal_tcn(input_dim=1, sequence_length=12)
codec = NeuralGraphCodec(spec)
print(spec.as_dict())
print(codec.describe())
```

**预期输出：** 构造本条目对应网络结构与未解析backend描述；精确布局须由正式Trainer/L0后端上下文解析，没有在组件内自行开启后端。

**依赖与边界：** NumPy与统一环境；实际parameter_layout(context=...)与网络求值另需正式ML调用提供支持该架构的backend.session。

**接口依据：** `mlblack.representations.codecs.neural.specs:NeuralGraphSpec.temporal_tcn`

## mlblack.codec.neural_temporal_tft_spec

构建 Temporal Fusion Transformer (TFT) 风格的 NeuralGraphSpec 路由，含门控残差网络和可解释多头自注意力。

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.representations.codecs.neural.specs import NeuralGraphSpec
from mlblack.representations.codecs.neural.base import NeuralGraphCodec
spec = NeuralGraphSpec.temporal_tft(input_dim=1, sequence_length=12)
codec = NeuralGraphCodec(spec)
print(spec.as_dict())
print(codec.describe())
```

**预期输出：** 构造本条目对应网络结构与未解析backend描述；精确布局须由正式Trainer/L0后端上下文解析，没有在组件内自行开启后端。

**依赖与边界：** NumPy与统一环境；实际parameter_layout(context=...)与网络求值另需正式ML调用提供支持该架构的backend.session。

**接口依据：** `mlblack.representations.codecs.neural.specs:NeuralGraphSpec.temporal_tft`

## mlblack.codec.neural_temporal_transformer_spec

构建时序 Transformer 预测的 NeuralGraphSpec 路由，通过后端神经网络降层执行。

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.representations.codecs.neural.specs import NeuralGraphSpec
from mlblack.representations.codecs.neural.base import NeuralGraphCodec
spec = NeuralGraphSpec.temporal_transformer(input_dim=1, sequence_length=12)
codec = NeuralGraphCodec(spec)
print(spec.as_dict())
print(codec.describe())
```

**预期输出：** 构造本条目对应网络结构与未解析backend描述；精确布局须由正式Trainer/L0后端上下文解析，没有在组件内自行开启后端。

**依赖与边界：** NumPy与统一环境；实际parameter_layout(context=...)与网络求值另需正式ML调用提供支持该架构的backend.session。

**接口依据：** `mlblack.representations.codecs.neural.specs:NeuralGraphSpec.temporal_transformer`

## mlblack.codec.neural_tabular_tabnet_spec

构建 TabNet 风格表格深度学习的 NeuralGraphSpec 路由，含特征 Transformer、注意力掩码和 GLU 激活。

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.representations.codecs.neural.specs import NeuralGraphSpec
from mlblack.representations.codecs.neural.base import NeuralGraphCodec
spec = NeuralGraphSpec.tabular_tabnet(input_dim=2, hidden_dim=8)
codec = NeuralGraphCodec(spec)
print(spec.as_dict())
print(codec.describe())
```

**预期输出：** 构造本条目对应网络结构与未解析backend描述；精确布局须由正式Trainer/L0后端上下文解析，没有在组件内自行开启后端。

**依赖与边界：** NumPy与统一环境；实际parameter_layout(context=...)与网络求值另需正式ML调用提供支持该架构的backend.session。

**接口依据：** `mlblack.representations.codecs.neural.specs:NeuralGraphSpec.tabular_tabnet`

## mlblack.codec.neural_graph

Decode a flat parameter state into a neural model from NeuralGraphSpec.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.representations.codecs.neural.base import NeuralGraphCodec
codec = NeuralGraphCodec.mlp(input_dim=2, hidden_layers=(4,), output_dim=1)
values = codec.init_values()
print(values.shape)
print(codec.parameter_layout())
```

**预期输出：** 一个2→4→1网络的参数向量和布局；布局状态不属于搜索Adapter Unit。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.codecs.neural.base:NeuralGraphCodec`

## mlblack.codec.symbolic_expression

Fixed symbolic expression codec.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.representations.codecs.symbolic import SymbolicExpressionCodec, SymbolicExpressionCodecConfig
codec = SymbolicExpressionCodec(SymbolicExpressionCodecConfig(input_dim=1, expression={'type': 'binary', 'op': 'mul', 'left': {'type': 'param', 'name': 'slope', 'init': 2.0}, 'right': {'type': 'feature', 'index': 0}}))
model = codec.decode(codec.init_values())
print(model.predict(np.array([[1.], [2.]])))
print(codec.encode(model))
```

**预期输出：** 固定表达式2*x0的预测和可训练参数向量；这里不搜索表达式结构。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.codecs.symbolic:SymbolicExpressionCodec`

## mlblack.codec.symbolic_multi_expression

Fixed multi-expression codec used by basis-set heads.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.representations.codecs.symbolic import SymbolicMultiExpressionCodec, SymbolicMultiExpressionCodecConfig
codec = SymbolicMultiExpressionCodec(SymbolicMultiExpressionCodecConfig(input_dim=1, genome=({'type': 'binary', 'op': 'mul', 'left': {'type': 'param', 'name': 'slope', 'init': 2.0}, 'right': {'type': 'feature', 'index': 0}},)))
values = codec.init_values()
model = codec.decode_term(0, values)
print(model.predict(np.array([[1.], [2.]])))
print(codec.blocks())
```

**预期输出：** 第0个表达式的参数块及预测；多表达式不能被当成一个没有分块的普通线性向量。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.codecs.symbolic:SymbolicMultiExpressionCodec`

## mlblack.representation.linear_point

**什么时候用：** 用搜索或梯度算法调整线性回归参数，同时需要保留模型布局、特征名和语义候选身份。它组合 LinearPointCodec 与输出 Head；默认 PointHead 表示每个样本一个数值预测。

**先准备什么：** `data` 是本 Case 的 NumericDataView，`data.X_train` 为 `(n,p)`，特征名顺序已经确认。默认 PointHead 下声明维数是 `p+1`，本例 `p=2` 所以候选值为 `(3,)`。更换为区间等 Head 时参数维数由 Head 决定，不能继续硬写 3。

**放在哪：** 在 Case 的 `pipeline/` 模型工厂或规范 `build_solver.py` 构造。正式 `catalog_codec_demo/cases/linear_point/build_solver.py` 在拿到 DataView 后构造它，再传给 `build_learning_solver(representation=...)`。

**接入步骤：**

```python
from mlblack.representations import LinearPointConfig, LinearPointRepresentation

def build_representation(data, *, seed=17):
    return LinearPointRepresentation(LinearPointConfig(
        n_features=data.n_features,
        feature_names=data.effective_feature_names,
        random_seed=int(seed),
    ))
```

`data` 由同 Case 的数据工厂传入，`seed` 来自 Case 配置。构造完 Representation 即可读 `dimension`，无需先调用 `init` 猜维数。先构造 LearningSolver 与其 SolutionPool，再让 Solver 的正式初始化创建 `UnknownState` 候选并绑定 token；解码模型与算法创建 Unit 是两个不同过程。

**运行入口：** 从 mlblack 仓库根目录使用 `python examples/cases/catalog_codec_demo/run_project.py --no-record`；完整装配见其 `cases/linear_point/build_solver.py`。本轮未执行。

**怎样判断接对：** `representation.dimension==3`，训练候选保留语义 metadata，解码模型有两个权重且预测 shape 为 `(n,)`。反馈与模型通过已评估候选 token 关联；不能按参数数组相等来猜“哪个模型”。输出不是立即训练好的模型，正式运行后才有评估过的最佳状态与模型投影。

**配套组件 key：** `mlblack.data_view.numeric`、`mlblack.codec.linear_point`、`mlblack.head.point`、`mlblack.problem.supervised_regression`、`mlblack.integration.learning_solver`。

**接口依据与验证状态：** `mlblack.representations.linear_point:LinearPointRepresentation` 与上述正式 Case；仅源码核对。

## mlblack.representation.orthogonal_linear / mlblack.representation.orthogonal_point_linear

Unknown vector decoded through orthogonal feature map and output head.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.representations.orthogonal_point import OrthogonalPointLinearRepresentation
representation = OrthogonalPointLinearRepresentation.from_data(X)
state = representation.init({})
print(representation.decode(state).predict(X))
```

**预期输出：** 两个Catalog键是同一类型；正交映射只由训练数据构建，预测复用冻结映射。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.orthogonal_point:OrthogonalPointLinearRepresentation`, `mlblack.representations.orthogonal_point:OrthogonalPointLinearRepresentation`

## mlblack.representation.neural_graph

Unknown vector -> configured neural graph model.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.representations.neural_graph import NeuralGraphRepresentation
from mlblack.representations.codecs.neural.specs import NeuralGraphSpec
representation = NeuralGraphRepresentation(NeuralGraphSpec.mlp(input_dim=2, hidden_layers=(4,), output_dim=1))
print(representation.dimension)
print(representation.describe())
```

**预期输出：** 已声明模型维数与图布局；没有为了推断shape而先抽一次初始解。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.neural_graph:NeuralGraphRepresentation`

## mlblack.representation.estimator_spec

Unknown vector decoded into a typed external estimator spec.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from sklearn.tree import DecisionTreeRegressor
from mlblack.representations.estimator_specs import EstimatorSpecRepresentation, EstimatorRouteConfig
representation = EstimatorSpecRepresentation(EstimatorRouteConfig(family='tree',
    route='sklearn.tree.DecisionTreeRegressor', tunable_params=('max_depth',),
    bounds={'max_depth': (2, 8)}, integer_params=('max_depth',),
    factory=lambda parameters: DecisionTreeRegressor(**parameters)))
state = representation.init({})
model_spec = representation.decode(state)
print(model_spec.describe())
print(type(model_spec.build_estimator()).__name__)
```

**预期输出：** 生成待拟合参数声明，再经显式factory构建估计器；真正fit仍属于Problem/Provider。

**依赖与边界：** NumPy、scikit-learn；route名称不是自动导入入口，factory必须显式准备。

**接口依据：** `mlblack.representations.estimator_specs:EstimatorSpecRepresentation`

## mlblack.representation.symbolic_expression

Fixed symbolic expression -> point/interval/probability head.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.representations.symbolic import SymbolicExpressionRepresentation, SymbolicExpressionConfig
representation = SymbolicExpressionRepresentation(SymbolicExpressionConfig(input_dim=1, expression={'type': 'binary', 'op': 'mul', 'left': {'type': 'param', 'name': 'slope', 'init': 2.0}, 'right': {'type': 'feature', 'index': 0}}))
print(representation.decode(representation.init({})).predict(np.array([[1.], [2.]])))
```

**预期输出：** 固定符号结构的模型预测；候选仅包含可训练数值参数。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.symbolic:SymbolicExpressionRepresentation`

## mlblack.representation.symbolic_basis_set

Fixed multi-expression symbolic candidate -> basis-set output.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.representations.symbolic import SymbolicBasisSetRepresentation, SymbolicBasisSetConfig
representation = SymbolicBasisSetRepresentation(SymbolicBasisSetConfig(input_dim=1, genome=({'type': 'binary', 'op': 'mul', 'left': {'type': 'param', 'name': 'slope', 'init': 2.0}, 'right': {'type': 'feature', 'index': 0}},)))
model = representation.decode(representation.init({}))
print(model.transform(np.array([[1.], [2.]])))
```

**预期输出：** 按表达式块产生基函数矩阵；不声称已经拟合一个回归器。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.symbolic:SymbolicBasisSetRepresentation`

## mlblack.representation.piecewise

Concatenates branch states and decodes a routed piecewise model.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.representations.conditional import PiecewiseRepresentation
from mlblack.representations.linear_point import LinearPointRepresentation
from mlblack.models.conditional import ThresholdRouter
representation = PiecewiseRepresentation(router=ThresholdRouter(0, (1.5,)),
    branches=(LinearPointRepresentation.from_data(X), LinearPointRepresentation.from_data(X)))
state = representation.init({})
print(representation.decode(state).predict(X))
```

**预期输出：** 阈值路由到两个独立参数块的线性分支；共享输入数据不等于共享可写优化状态。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.conditional:PiecewiseRepresentation`

## mlblack.representation.baseline_forecast / mlblack.representation.baseline_forecast_search

UnknownState -> Naive/seasonal-naive/moving-average forecast model.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.representations.time_series import BaselineForecastRepresentation, BaselineForecastSearchConfig
representation = BaselineForecastRepresentation(BaselineForecastSearchConfig(strategies=('naive', 'moving_average')))
model = representation.decode(representation.init({}))
print(model.forecast(series.y, horizon=3))
```

**预期输出：** 初始化一个基线策略候选并预测3步；配置和表示两个目录项在片段中都实际使用。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.time_series:BaselineForecastRepresentation`, `mlblack.representations.time_series:BaselineForecastSearchConfig`

## mlblack.representation.forecast_model_spec

Single-candidate Codec that decodes a declarative forecast fit spec; fitting belongs to the ML Problem/Provider.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.representations.time_series import ForecastModelSpecRepresentation
from mlblack.models.time_series import ARIMASARIMAXSpec
representation = ForecastModelSpecRepresentation(ARIMASARIMAXSpec(order=(1, 0, 0)))
spec = representation.decode(representation.init({}))
print(spec.describe())
```

**预期输出：** 把固定预测Spec作为语义候选；这一步尚未拟合时序模型。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.representations.time_series:ForecastModelSpecRepresentation`

## mlblack.model.linear_point

Decoded point model: f(x) = intercept + X @ weights.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.linear import LinearPointModel
base = LinearPointModel(intercept=1., weights=np.array([2., -0.5]))
print(base.predict(X))
```

**预期输出：** 4行点预测；模型保存intercept/weights，不拥有训练循环。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.linear:LinearPointModel`

## mlblack.model.numpy_mlp_point

Small decoded MLP point model backed by numpy arrays.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.neural import NumpyMLPPointModel
model = NumpyMLPPointModel(weights=(np.ones((2, 3)), np.ones((3, 1))),
    biases=(np.zeros(3), np.zeros(1)))
print(model.predict(X))
```

**预期输出：** 2→3→1纯NumPy前向预测；没有假设网络已经训练。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.neural:NumpyMLPPointModel`

## mlblack.model.binary_logistic_probability

Probability wrapper around a scalar logit model.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.linear import LinearPointModel
base = LinearPointModel(intercept=1., weights=np.array([2., -0.5]))
from mlblack.models.probability import BinaryLogisticProbabilityModel
model = BinaryLogisticProbabilityModel(logit_model=base)
print(model.predict_proba(X))
```

**预期输出：** 4个输入样本逐行输出本模型声明的概率/区间/分布；这些输出与普通点预测不可混淆。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.probability:BinaryLogisticProbabilityModel`

## mlblack.model.softmax_probability

Probability wrapper around one scalar logit model per class.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.linear import LinearPointModel
base = LinearPointModel(intercept=1., weights=np.array([2., -0.5]))
from mlblack.models.probability import SoftmaxProbabilityModel
model = SoftmaxProbabilityModel(logit_models=(base, base))
print(model.predict_proba(X))
```

**预期输出：** 4个输入样本逐行输出本模型声明的概率/区间/分布；这些输出与普通点预测不可混淆。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.probability:SoftmaxProbabilityModel`

## mlblack.model.temperature_calibrated_probability

Temperature calibration wrapper for probability-capable models.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.linear import LinearPointModel
base = LinearPointModel(intercept=1., weights=np.array([2., -0.5]))
from mlblack.models.probability import TemperatureCalibratedProbabilityModel
model = TemperatureCalibratedProbabilityModel(base_model=base, temperature=2.0)
print(model.predict_proba(X))
```

**预期输出：** 4个输入样本逐行输出本模型声明的概率/区间/分布；这些输出与普通点预测不可混淆。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.probability:TemperatureCalibratedProbabilityModel`

## mlblack.model.probability_calibration

Simple probability calibration wrapper.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.linear import LinearPointModel
base = LinearPointModel(intercept=1., weights=np.array([2., -0.5]))
from mlblack.models.probability import BinaryLogisticProbabilityModel
base = BinaryLogisticProbabilityModel(logit_model=base)
from mlblack.models.conditional import ProbabilityCalibrationModel
model = ProbabilityCalibrationModel(base_model=base, temperature=2.0)
print(model.predict_proba(X))
```

**预期输出：** 4个输入样本逐行输出本模型声明的概率/区间/分布；这些输出与普通点预测不可混淆。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.conditional:ProbabilityCalibrationModel`

## mlblack.model.interval_prediction

Two-bound interval predictor built from lower and upper models.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.linear import LinearPointModel
base = LinearPointModel(intercept=1., weights=np.array([2., -0.5]))
from mlblack.models.outputs import IntervalPredictionModel
model = IntervalPredictionModel(lower_model=base, upper_model=base)
print(model.predict_interval(X))
```

**预期输出：** 4个输入样本逐行输出本模型声明的概率/区间/分布；这些输出与普通点预测不可混淆。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.outputs:IntervalPredictionModel`

## mlblack.model.center_radius_interval

Interval predictor built from center and radius models.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.linear import LinearPointModel
base = LinearPointModel(intercept=1., weights=np.array([2., -0.5]))
from mlblack.models.outputs import CenterRadiusIntervalModel
model = CenterRadiusIntervalModel(center_model=base, radius_model=base)
print(model.predict_interval(X))
```

**预期输出：** 4个输入样本逐行输出本模型声明的概率/区间/分布；这些输出与普通点预测不可混淆。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.outputs:CenterRadiusIntervalModel`

## mlblack.model.normal_distribution

NormalDistributionModel(mu_model: 'Any', sigma_model: 'Any', sigma_transform: 'str' = 'softplus', metadata: 'Mapping[str, Any]' = <factory>)

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.linear import LinearPointModel
base = LinearPointModel(intercept=1., weights=np.array([2., -0.5]))
from mlblack.models.distributions import NormalDistributionModel
model = NormalDistributionModel(mu_model=base, sigma_model=base)
print(model.predict_params(X))
```

**预期输出：** 4个输入样本逐行输出本模型声明的概率/区间/分布；这些输出与普通点预测不可混淆。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.distributions:NormalDistributionModel`

## mlblack.model.poisson_distribution

PoissonDistributionModel(rate_model: 'Any', rate_transform: 'str' = 'softplus', metadata: 'Mapping[str, Any]' = <factory>)

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.linear import LinearPointModel
base = LinearPointModel(intercept=1., weights=np.array([2., -0.5]))
from mlblack.models.distributions import PoissonDistributionModel
model = PoissonDistributionModel(rate_model=base)
print(model.predict_params(X))
```

**预期输出：** 4个输入样本逐行输出本模型声明的概率/区间/分布；这些输出与普通点预测不可混淆。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.distributions:PoissonDistributionModel`

## mlblack.model.negative_binomial_distribution

NegativeBinomialDistributionModel(mu_model: 'Any', alpha_model: 'Any', alpha_transform: 'str' = 'softplus', metadata: 'Mapping[str, Any]' = <factory>)

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.linear import LinearPointModel
base = LinearPointModel(intercept=1., weights=np.array([2., -0.5]))
from mlblack.models.distributions import NegativeBinomialDistributionModel
model = NegativeBinomialDistributionModel(mu_model=base, alpha_model=base)
print(model.predict_params(X))
```

**预期输出：** 4个输入样本逐行输出本模型声明的概率/区间/分布；这些输出与普通点预测不可混淆。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.distributions:NegativeBinomialDistributionModel`

## mlblack.model.orthogonal_feature_map

Data-side feature map used by decoded point models.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.linear import OrthogonalFeatureMap
feature_map = OrthogonalFeatureMap.fit(X, feature_names=('a','b'))
print(feature_map.transform(X))
```

**预期输出：** 在训练数据上拟合并应用正交特征映射；预测数据只transform。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.linear:OrthogonalFeatureMap`

## mlblack.model.orthogonal_linear_point

Decoded point model: f(x) = intercept + Q(x) @ weights.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.linear import OrthogonalFeatureMap, OrthogonalLinearPointModel
fmap = OrthogonalFeatureMap.fit(X)
model = OrthogonalLinearPointModel(feature_map=fmap, intercept=1., weights=np.ones(fmap.output_dim))
print(model.predict(X))
```

**预期输出：** 使用同一冻结feature_map解释权重并预测4行。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.linear:OrthogonalLinearPointModel`

## mlblack.model.router / mlblack.model.threshold_router

Auto-discovered mlblack component `model.router`.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.conditional import Router, ThresholdRouter
router: Router = ThresholdRouter(feature_index=0, thresholds=(1.5,))
print(router.route(X))
```

**预期输出：** 路由编号[0,0,1,1]；Router是扩展协议，ThresholdRouter是这里实际实例化的实现。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.conditional:Router`, `mlblack.models.conditional:ThresholdRouter`

## mlblack.model.piecewise

PiecewiseModel(router: 'Router', branch_models: 'Sequence[Any]', default_branch: 'int' = 0, metadata: 'Mapping[str, Any]' = <factory>)

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.linear import LinearPointModel
base = LinearPointModel(intercept=1., weights=np.array([2., -0.5]))
from mlblack.models.conditional import PiecewiseModel, ThresholdRouter
model = PiecewiseModel(router=ThresholdRouter(0, (1.5,)), branch_models=(base, base))
print(model.predict(X))
```

**预期输出：** 按行路由并从对应已准备分支取预测；不在该对象里进行多Case调度。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.conditional:PiecewiseModel`

## mlblack.model.prediction_input

Input requirement for one component model inside an integrated model.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.composition import PredictionInputSpec
spec = PredictionInputSpec(key='features', n_features=2)
print(spec.validate(X, component_name='linear'))
```

**预期输出：** 输入按二维2特征契约验证，不兼容shape会显式拒绝。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.composition:PredictionInputSpec`

## mlblack.model.prediction_output

Output requirement consumed by the integration strategy.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.models.composition import PredictionOutputSpec
spec = PredictionOutputSpec(kind='point_vector')
print(spec.validate_prediction(np.array([[1.], [2.]]), component_name='linear'))
```

**预期输出：** 单列预测被规范为长度2的点预测向量；多列分类概率不能冒充点输出。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.composition:PredictionOutputSpec`

## mlblack.model.prediction_io

I/O contract for routing inputs and validating component predictions.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.composition import PredictionIOContract, PredictionInputSpec
contract = PredictionIOContract.by_component({'linear': PredictionInputSpec(key='features', n_features=2)})
print(contract.component_input({'features': X}, component_name='linear'))
```

**预期输出：** 按显式key读取并验证这个子模型的输入；没有按名称猜数据流。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.composition:PredictionIOContract`

## mlblack.model.prediction_integration / mlblack.model.integrated_prediction / mlblack.model.prediction_integration_component

How named model predictions are combined into one prediction.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.linear import LinearPointModel
base = LinearPointModel(intercept=1., weights=np.array([2., -0.5]))
from mlblack.models.composition import PredictionIntegrationSpec, PredictionIntegrationComponent, IntegratedPredictionModel
spec = PredictionIntegrationSpec(kind='additive', component_order=('baseline','residual'), weights={'residual': 0.2})
component = PredictionIntegrationComponent(integration=spec)
model = component.compose({'baseline': base, 'residual': base})
assert isinstance(model, IntegratedPredictionModel)
print(model.predict(X))
```

**预期输出：** 组合两个已拟合模型的逐行预测；这是推理语义，不会自动安排训练顺序。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.composition:PredictionIntegrationSpec`, `mlblack.models.composition:IntegratedPredictionModel`, `mlblack.models.composition:PredictionIntegrationComponent`

## mlblack.model.estimator_spec

Decoded external estimator specification.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from sklearn.tree import DecisionTreeRegressor
from mlblack.models.estimators import EstimatorSpecModel
model_spec = EstimatorSpecModel(family='tree', route='sklearn.tree.DecisionTreeRegressor',
    params={'max_depth': 3}, factory=lambda parameters: DecisionTreeRegressor(**parameters))
print(model_spec.describe())
print(type(model_spec.build_estimator()).__name__)
```

**预期输出：** Spec保存route/参数并通过明确factory创建估计器；不传factory会在build_estimator显式拒绝，不偷偷调用训练。

**依赖与边界：** NumPy、scikit-learn；factory是明确的外部估计器构造边界。

**接口依据：** `mlblack.models.estimators:EstimatorSpecModel`

## mlblack.model.fitted_estimator

Prediction wrapper around an already fitted external estimator.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from sklearn.linear_model import LinearRegression
from mlblack.models.estimators import FittedEstimatorModel
estimator = LinearRegression().fit(X, y)
model = FittedEstimatorModel(estimator=estimator, family='linear', route='sklearn.linear_model.LinearRegression')
print(model.predict(X))
```

**预期输出：** 包装一个已拟合估计器并预测；正式训练应在ML Problem/Provider内执行。

**依赖与边界：** NumPy、scikit-learn；该片段演示模型封装，不另造训练控制面。

**接口依据：** `mlblack.models.estimators:FittedEstimatorModel`

## mlblack.model.naive_forecast

Naive, seasonal-naive, or moving-average univariate forecaster.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.models.time_series import NaiveForecastModel
model = NaiveForecastModel(strategy='moving_average', window=3)
print(model.forecast(series.y, horizon=3))
```

**预期输出：** 最近3个观测构成的3步预测；严格使用给定历史。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.time_series:NaiveForecastModel`

## mlblack.model.linear_autoregressive_fit_spec / mlblack.model.linear_autoregressive_forecast

Declarative AR/ARX closed-form fitting request materialized by the time-series Problem.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.models.time_series import LinearAutoregressiveFitSpec, LinearAutoregressiveForecastModel
from mlblack.pipeline.time_series import TimeSeriesWindowConfig
spec = LinearAutoregressiveFitSpec(window_config=TimeSeriesWindowConfig(lags=(1,2), horizon=1), ridge=1e-6)
model = LinearAutoregressiveForecastModel.fit(series, spec.window_config, ridge=spec.ridge)
print(model.forecast(series.y, horizon=3))
```

**预期输出：** 时序滞后特征拟合后的3步递归预测；不是把未来目标作为当前输入。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.time_series:LinearAutoregressiveFitSpec`, `mlblack.models.time_series:LinearAutoregressiveForecastModel`

## mlblack.model.lag_estimator_forecast

Forecast wrapper around an already-fitted lag-feature estimator.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from sklearn.linear_model import Ridge
from mlblack.models.time_series import LagEstimatorForecastModel
from mlblack.pipeline.time_series import TimeSeriesWindowConfig
model = LagEstimatorForecastModel.fit(Ridge(alpha=1e-3), series, TimeSeriesWindowConfig(lags=(1,2)))
print(model.forecast(series.y, horizon=3))
```

**预期输出：** 使用明确的滞后配置创建表格估计器预测模型。

**依赖与边界：** NumPy、scikit-learn；正式fit放在Case Problem/Provider。

**接口依据：** `mlblack.models.time_series:LagEstimatorForecastModel`

## mlblack.model.arimasarimax / mlblack.model.arimasarimax_forecast

Declarative ARIMA/SARIMAX order and fitting options.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.models.time_series import ARIMASARIMAXSpec, ARIMASARIMAXProvider, ARIMASARIMAXForecastModel
spec = ARIMASARIMAXSpec(order=(1,0,0), backend='numpy_fallback')
model = ARIMASARIMAXProvider(spec).fit(series)
assert isinstance(model, ARIMASARIMAXForecastModel)
print(model.forecast(series.y, horizon=3))
```

**预期输出：** 明确选择NumPy fallback得到已拟合模型；fallback不声称支持statsmodels全部ARIMA语义。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.time_series:ARIMASARIMAXSpec`, `mlblack.models.time_series:ARIMASARIMAXForecastModel`

## mlblack.model.statsmodels_sarimax_forecast

Forecast wrapper around a fitted statsmodels SARIMAXResults object.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.models.time_series import ARIMASARIMAXSpec, ARIMASARIMAXProvider, StatsmodelsSARIMAXForecastModel
model = ARIMASARIMAXProvider(ARIMASARIMAXSpec(order=(1,0,0), backend='statsmodels')).fit(series)
assert isinstance(model, StatsmodelsSARIMAXForecastModel)
print(model.forecast(series.y, horizon=3))
```

**预期输出：** 真正statsmodels结果对象的3步预测包装；不能在缺依赖时冒称该后端已启用。

**依赖与边界：** NumPy、statsmodels；正式拟合消耗的资源由Project L0授权。

**接口依据：** `mlblack.models.time_series:StatsmodelsSARIMAXForecastModel`

## mlblack.model.symbolic_expression

Decoded symbolic point model with fitted parameter values.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.models.symbolic import SymbolicExpressionModel, ParameterSpec
model = SymbolicExpressionModel(name='scaled_x0', expression={'type': 'binary', 'op': 'mul', 'left': {'type': 'param', 'name': 'slope', 'init': 2.0}, 'right': {'type': 'feature', 'index': 0}},
    parameter_specs=(ParameterSpec('slope', init=2.0),), param_values={'slope': 2.0}, input_dim=1)
print(model.predict(np.array([[1.], [2.]])))
```

**预期输出：** 已给定结构和数值参数的符号模型预测；结构搜索不在模型对象里。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.symbolic:SymbolicExpressionModel`

## mlblack.model.symbolic_basis_set

Decoded multi-expression output used by orthogonal basis search.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.models.symbolic import SymbolicBasisSetModel
from mlblack.representations.codecs.symbolic import SymbolicExpressionCodec, SymbolicExpressionCodecConfig
codec = SymbolicExpressionCodec(SymbolicExpressionCodecConfig(input_dim=1, expression={'type': 'binary', 'op': 'mul', 'left': {'type': 'param', 'name': 'slope', 'init': 2.0}, 'right': {'type': 'feature', 'index': 0}}))
model = SymbolicBasisSetModel(atoms=(codec.decode(codec.init_values()),))
print(model.transform(np.array([[1.], [2.]])))
```

**预期输出：** 按atoms顺序生成基函数矩阵；没有自动拟合基函数的线性系数。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.models.symbolic:SymbolicBasisSetModel`

## mlblack.pipeline.identity

Data pipeline component.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.data_views.numeric import NumericDataView
data = NumericDataView(X_train=X, y_train=y, feature_names=('a', 'b'))
from mlblack.pipeline.components import IdentityComponent
component = IdentityComponent()
prepared, state = component.fit_transform(data)
print(prepared.describe())
print(state)
```

**预期输出：** 对训练数据fit，再transform；validation使用同一fit-state，避免独立拟合造成数据泄漏。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.components:IdentityComponent`

## mlblack.pipeline.select_columns

SelectColumnsComponent(columns: 'Sequence[int]' = ())

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.data_views.numeric import NumericDataView
data = NumericDataView(X_train=X, y_train=y, feature_names=('a', 'b'))
from mlblack.pipeline.components import SelectColumnsComponent
component = SelectColumnsComponent(columns=(0,))
prepared, state = component.fit_transform(data)
print(prepared.describe())
print(state)
```

**预期输出：** 对训练数据fit，再transform；validation使用同一fit-state，避免独立拟合造成数据泄漏。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.components:SelectColumnsComponent`

## mlblack.pipeline.z_score_normalize

ZScoreNormalizeComponent(eps: 'float' = 1e-12, with_mean: 'bool' = True, with_std: 'bool' = True)

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.data_views.numeric import NumericDataView
data = NumericDataView(X_train=X, y_train=y, feature_names=('a', 'b'))
from mlblack.pipeline.components import ZScoreNormalizeComponent
component = ZScoreNormalizeComponent()
prepared, state = component.fit_transform(data)
print(prepared.describe())
print(state)
```

**预期输出：** 对训练数据fit，再transform；validation使用同一fit-state，避免独立拟合造成数据泄漏。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.components:ZScoreNormalizeComponent`

## mlblack.pipeline.data_pipeline / mlblack.pipeline.data_pipeline_chain

Data pipeline component.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.data_views.numeric import NumericDataView
data = NumericDataView(X_train=X, y_train=y, feature_names=('a', 'b'))
from mlblack.pipeline.base import DataPipeline, DataPipelineComponent
from mlblack.pipeline.components import SelectColumnsComponent, ZScoreNormalizeComponent
components: tuple[DataPipelineComponent, ...] = (SelectColumnsComponent(columns=(0,)), ZScoreNormalizeComponent())
pipeline = DataPipeline(components)
prepared = pipeline.fit_transform(data)
print(prepared.describe())
print(pipeline.describe())
```

**预期输出：** 按顺序选择第0列再标准化；基础DataPipelineComponent协议由具体组件消费。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.base:DataPipelineComponent`, `mlblack.pipeline.base:DataPipeline`

## mlblack.pipeline.feature_space

Records feature-space metadata in the data pipeline.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.data_views.numeric import NumericDataView
data = NumericDataView(X_train=X, y_train=y, feature_names=('a', 'b'))
from mlblack.pipeline.feature_space import FeatureSpaceComponent
component = FeatureSpaceComponent(group='all')
prepared, state = component.fit_transform(data)
print(state)
print(prepared.n_features)
```

**预期输出：** 产出轻量特征空间描述，并保持候选和优化状态由各自所有者管理。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.feature_space:FeatureSpaceComponent`

## mlblack.pipeline.conditional_primitive_feature

Append deterministic conditional primitive features to NumericDataView.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.data_views.numeric import NumericDataView
data = NumericDataView(X_train=X, y_train=y, feature_names=('a', 'b'))
from mlblack.pipeline.feature_space import ConditionalPrimitiveFeatureComponent
from mlblack.pipeline.conditional.primitives import HingeFeature
component = ConditionalPrimitiveFeatureComponent(primitives=(HingeFeature(0, 1.5),), include_original=True)
prepared = component.transform(data)
print(prepared.X_train)
```

**预期输出：** 原始两列后附一列hinge特征，输出4×3；没有在数据管线里训练模型。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.feature_space:ConditionalPrimitiveFeatureComponent`

## mlblack.pipeline.numeric_batch_loader

Batch iterator over a NumericDataView.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.data_views.numeric import NumericDataView
data = NumericDataView(X_train=X, y_train=y, feature_names=('a', 'b'))
from mlblack.pipeline.datasets import NumericBatchLoader, DatasetStreamConfig
loader = NumericBatchLoader(data, DatasetStreamConfig(batch_size=2, shuffle=False))
batch = next(iter(loader.iter_train()))
print(batch.X, batch.y, batch.indices)
```

**预期输出：** 第一批2个样本及其原始行号；schedule还负责可恢复的数据游标，不代替Solver代数。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.datasets:NumericBatchLoader`

## mlblack.pipeline.numeric_batch_schedule

可恢复的数值 batch/epoch 调度器；拥有 shuffle、cursor 和 epoch 状态，不拥有优化算法。

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.data_views.numeric import NumericDataView
data = NumericDataView(X_train=X, y_train=y, feature_names=('a', 'b'))
from mlblack.pipeline.datasets import NumericBatchSchedule, DatasetStreamConfig
loader = NumericBatchSchedule(data, DatasetStreamConfig(batch_size=2, shuffle=False))
batch = loader.next_train()
print(batch.X, batch.y, batch.indices)
```

**预期输出：** 第一批2个样本及其原始行号；schedule还负责可恢复的数据游标，不代替Solver代数。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.datasets:NumericBatchSchedule`

## mlblack.pipeline.row_dataset_stream

Lightweight row streaming surface for local or external datasets.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.pipeline.datasets import RowDatasetStream, DatasetStreamConfig
stream = RowDatasetStream([{'x': 1, 'target': 2}, {'x': 3, 'target': 4}], DatasetStreamConfig(batch_size=1))
batch = next(stream.iter_batches())
print(batch.rows, batch.indices)
```

**预期输出：** 首批1条原始记录及其索引；没有强行把非数值列转成浮点。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.datasets:RowDatasetStream`

## mlblack.pipeline.tokenized_text_dataset_builder

Build token-id NumericDataView objects from text datasets.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.pipeline.datasets import TokenizedTextDatasetBuilder, TokenizedTextDatasetConfig
from mlblack.pipeline.numericizer.text import VocabularyTokenizer
tokenizer = VocabularyTokenizer().fit(['good item', 'bad item'])
builder = TokenizedTextDatasetBuilder(tokenizer, TokenizedTextDatasetConfig(max_length=4))
data = builder.from_rows([{'text':'good item', 'label':1}, {'text':'bad item', 'label':0}])
print(data.describe())
```

**预期输出：** 文本先经显式词表数值化，再交付二维token特征和标签；词表是可保存状态。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.datasets:TokenizedTextDatasetBuilder`

## mlblack.numericizer.vocabulary_tokenizer

Small local tokenizer/numericizer for transformer smoke tasks.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.pipeline.numericizer.text import VocabularyTokenizer, VocabularyTokenizerConfig
tokenizer = VocabularyTokenizer(VocabularyTokenizerConfig(max_length=4))
values = tokenizer.fit_transform(['red car', 'blue car'])
print(values)
restored = VocabularyTokenizer.from_dict(tokenizer.as_dict())
print(restored.encode('red car'))
```

**预期输出：** 可保存/恢复词表的整数序列；新文本只能使用该词表规则。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.numericizer.text:VocabularyTokenizer`

## mlblack.numericizer.target

TargetCodec(kind: 'str' = 'numeric', classes: 'Sequence[Any]' = (), metadata: 'Mapping[str, Any]' = <factory>)

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.pipeline.numericizer.target_codec import TargetCodec
codec = TargetCodec(kind='categorical', classes=('low','high'))
encoded = codec.encode(['high','low'])
print(encoded)
print(codec.decode(encoded))
```

**预期输出：** 按固定类序编码为[1,0]并还原标签；没有从字符串排序猜业务类序。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.numericizer.target_codec:TargetCodec`

## mlblack.numericizer.default / mlblack.numericizer.default_numericizer

Converts schema-backed raw rows into NumericDataView.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.assembly.schema.spec import DatasetSchema, FeatureSpec, TargetSpec
from mlblack.pipeline.numericizer.plan import NumericizationPlan, NumericFeatureColumn
from mlblack.pipeline.numericizer.default import DefaultNumericizer
schema = DatasetSchema(features=(FeatureSpec(key='x', dtype='numeric'),), targets=(TargetSpec(key='target'),))
plan = NumericizationPlan(schema=schema, columns=(NumericFeatureColumn('x','x'),), target=schema.target)
view = DefaultNumericizer(plan).fit_transform([{'x':1, 'target':2}, {'x':3, 'target':4}])
print(view.describe())
```

**预期输出：** 原始行经明确schema/plan变成2×1数值监督视图；两个键是同一实现。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.numericizer.default:DefaultNumericizer`, `mlblack.pipeline.numericizer.default:DefaultNumericizer`

## mlblack.pipeline.time_series_window

Lag-window configuration for converting a series into supervised rows.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.pipeline.time_series import TimeSeriesWindowConfig, TimeSeriesWindowingComponent
config = TimeSeriesWindowConfig(lags=(1,2,3), horizon=1, valid_size=0.2)
component = TimeSeriesWindowingComponent(config)
prepared, state = component.fit_transform(series)
print(prepared.describe())
```

**预期输出：** 构建仅用过去滞后量的一步预测监督视图，并按时间留出验证区间。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.time_series:TimeSeriesWindowConfig`

## mlblack.pipeline.time_series_windowing

Convert TimeSeriesDataView into a lagged NumericDataView.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.pipeline.time_series import TimeSeriesWindowConfig, TimeSeriesWindowingComponent
config = TimeSeriesWindowConfig(lags=(1,2,3), horizon=1, valid_size=0.2)
component = TimeSeriesWindowingComponent(config)
prepared, state = component.fit_transform(series)
print(prepared.describe())
```

**预期输出：** 构建仅用过去滞后量的一步预测监督视图，并按时间留出验证区间。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.time_series:TimeSeriesWindowingComponent`

## mlblack.pipeline.seasonal_decomposition

STL-like additive seasonal decomposition configuration.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.pipeline.time_series import SeasonalDecompositionConfig, STLSeasonalDecompositionComponent, SeasonalDecompositionResult
config = SeasonalDecompositionConfig(period=7, residual_target=False)
component = STLSeasonalDecompositionComponent(config)
result, state = component.fit_transform(series)
assert isinstance(result, SeasonalDecompositionResult)
print(result.component_values('resid'))
print(result.to_data_view(component='resid').describe())
```

**预期输出：** 得到真实趋势/季节/残差结果，再选择resid转成时间序列DataView；residual_target=False明确要求保留分解结果对象。

**依赖与边界：** NumPy；当前实现是移动平均趋势加周期相位均值的stl_like分解，不是statsmodels STL拟合。

**接口依据：** `mlblack.pipeline.time_series:SeasonalDecompositionConfig`

## mlblack.pipeline.stl_seasonal_decomposition

STL-like deterministic seasonal decomposition for TimeSeriesDataView.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.pipeline.time_series import SeasonalDecompositionConfig, STLSeasonalDecompositionComponent, SeasonalDecompositionResult
config = SeasonalDecompositionConfig(period=7, residual_target=False)
component = STLSeasonalDecompositionComponent(config)
result, state = component.fit_transform(series)
assert isinstance(result, SeasonalDecompositionResult)
print(result.component_values('resid'))
print(result.to_data_view(component='resid').describe())
```

**预期输出：** 得到真实趋势/季节/残差结果，再选择resid转成时间序列DataView；residual_target=False明确要求保留分解结果对象。

**依赖与边界：** NumPy；当前实现是移动平均趋势加周期相位均值的stl_like分解，不是statsmodels STL拟合。

**接口依据：** `mlblack.pipeline.time_series:STLSeasonalDecompositionComponent`

## mlblack.pipeline.seasonal_decomposition_result

Trend, seasonal and residual arrays aligned to the original series.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.pipeline.time_series import SeasonalDecompositionConfig, STLSeasonalDecompositionComponent, SeasonalDecompositionResult
config = SeasonalDecompositionConfig(period=7, residual_target=False)
component = STLSeasonalDecompositionComponent(config)
result, state = component.fit_transform(series)
assert isinstance(result, SeasonalDecompositionResult)
print(result.component_values('resid'))
print(result.to_data_view(component='resid').describe())
```

**预期输出：** 得到真实趋势/季节/残差结果，再选择resid转成时间序列DataView；residual_target=False明确要求保留分解结果对象。

**依赖与边界：** NumPy；当前实现是移动平均趋势加周期相位均值的stl_like分解，不是statsmodels STL拟合。

**接口依据：** `mlblack.pipeline.time_series:SeasonalDecompositionResult`

## mlblack.pipeline.model_conditioned_target

Builds next-stage targets by calling an existing model, e.g. y - model.predict(X).

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.data_views.numeric import NumericDataView
data = NumericDataView(X_train=X, y_train=y, feature_names=('a', 'b'))
from mlblack.models.linear import LinearPointModel
from mlblack.pipeline.model_conditioning import ModelConditionedTargetComponent, ModelConditionedTargetConfig, ModelConditionedTargetBuilder
reference = LinearPointModel(intercept=1., weights=np.array([1.,0.]))
config = ModelConditionedTargetConfig(mode='residual', append_prediction_feature=True)
component = ModelConditionedTargetComponent(reference_model=reference, config=config)
prepared, state = component.fit_transform(data)
print(prepared.X_train, prepared.y_train)
builder = ModelConditionedTargetBuilder(reference_model=reference, config=config)
print(builder.build(data).describe())
```

**预期输出：** 以已准备的参考模型构造残差目标，并显式追加预测特征；参考模型不是在此管线偷偷训练出来。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.model_conditioning:ModelConditionedTargetComponent`

## mlblack.pipeline.model_conditioned_target_builder

Transforms data by calling an already-trained reference model.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.data_views.numeric import NumericDataView
data = NumericDataView(X_train=X, y_train=y, feature_names=('a', 'b'))
from mlblack.models.linear import LinearPointModel
from mlblack.pipeline.model_conditioning import ModelConditionedTargetComponent, ModelConditionedTargetConfig, ModelConditionedTargetBuilder
reference = LinearPointModel(intercept=1., weights=np.array([1.,0.]))
config = ModelConditionedTargetConfig(mode='residual', append_prediction_feature=True)
component = ModelConditionedTargetComponent(reference_model=reference, config=config)
prepared, state = component.fit_transform(data)
print(prepared.X_train, prepared.y_train)
builder = ModelConditionedTargetBuilder(reference_model=reference, config=config)
print(builder.build(data).describe())
```

**预期输出：** 以已准备的参考模型构造残差目标，并显式追加预测特征；参考模型不是在此管线偷偷训练出来。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.model_conditioning:ModelConditionedTargetBuilder`

## mlblack.pipeline.model_conditioned_target_config

Configuration for building a next-stage target from a reference model.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.data_views.numeric import NumericDataView
data = NumericDataView(X_train=X, y_train=y, feature_names=('a', 'b'))
from mlblack.models.linear import LinearPointModel
from mlblack.pipeline.model_conditioning import ModelConditionedTargetComponent, ModelConditionedTargetConfig, ModelConditionedTargetBuilder
reference = LinearPointModel(intercept=1., weights=np.array([1.,0.]))
config = ModelConditionedTargetConfig(mode='residual', append_prediction_feature=True)
component = ModelConditionedTargetComponent(reference_model=reference, config=config)
prepared, state = component.fit_transform(data)
print(prepared.X_train, prepared.y_train)
builder = ModelConditionedTargetBuilder(reference_model=reference, config=config)
print(builder.build(data).describe())
```

**预期输出：** 以已准备的参考模型构造残差目标，并显式追加预测特征；参考模型不是在此管线偷偷训练出来。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.model_conditioning:ModelConditionedTargetConfig`

## mlblack.pipeline.hive_query_source / mlblack.pipeline.source.hive_query

Run a SQL query against HiveServer2 and materialise the result set.

**输入与前提：** 在可信Case内先准备对应只读连接、数据列和必要驱动；域名/桶名为占位配置。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.pipeline.sources import HiveQuerySource
source = HiveQuerySource(host='hive.internal', database='demo', query='SELECT x, target FROM demo_table', target_column='target')
print(source.describe())
# 下面一行只在已授权且准备好后端的Case数据管线中运行。
prepared = source.transform(None)
print(prepared.describe())
```

**预期输出：** 从指定只读数据源装入数值视图；数据库驱动/访问凭据由部署提供，片段不携带真实秘密。

**依赖与边界：** Hive需pyhive；JDBC需Java/jaydebeapi与驱动；S3需s3fs/pyarrow。只演示所选源的依赖，不代表已联网。

**接口依据：** `mlblack.pipeline.sources:HiveQuerySource`, `mlblack.pipeline.sources:HiveQuerySource`

## mlblack.pipeline.jdbc_query_source / mlblack.pipeline.source.jdbc_query

Run a SQL query against any JDBC data source and materialise the result.

**输入与前提：** 在可信Case内先准备对应只读连接、数据列和必要驱动；域名/桶名为占位配置。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.pipeline.sources import JDBCQuerySource
source = JDBCQuerySource(jdbc_url='jdbc:postgresql://db.internal:5432/demo', driver_class='org.postgresql.Driver', driver_jar='/opt/drivers/postgresql.jar', query='SELECT x, target FROM demo_table', target_column='target')
print(source.describe())
# 下面一行只在已授权且准备好后端的Case数据管线中运行。
prepared = source.transform(None)
print(prepared.describe())
```

**预期输出：** 从指定只读数据源装入数值视图；数据库驱动/访问凭据由部署提供，片段不携带真实秘密。

**依赖与边界：** Hive需pyhive；JDBC需Java/jaydebeapi与驱动；S3需s3fs/pyarrow。只演示所选源的依赖，不代表已联网。

**接口依据：** `mlblack.pipeline.sources:JDBCQuerySource`, `mlblack.pipeline.sources:JDBCQuerySource`

## mlblack.pipeline.s3_parquet_source / mlblack.pipeline.source.s3_parquet

Read a Parquet dataset from S3 or an S3-compatible store (MinIO, etc.).

**输入与前提：** 在可信Case内先准备对应只读连接、数据列和必要驱动；域名/桶名为占位配置。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.pipeline.sources import S3ParquetSource
source = S3ParquetSource(bucket='public-demo-data', prefix='training/', target_column='target')
print(source.describe())
# 下面一行只在已授权且准备好后端的Case数据管线中运行。
prepared = source.transform(None)
print(prepared.describe())
```

**预期输出：** 从指定只读数据源装入数值视图；数据库驱动/访问凭据由部署提供，片段不携带真实秘密。

**依赖与边界：** Hive需pyhive；JDBC需Java/jaydebeapi与驱动；S3需s3fs/pyarrow。只演示所选源的依赖，不代表已联网。

**接口依据：** `mlblack.pipeline.sources:S3ParquetSource`, `mlblack.pipeline.sources:S3ParquetSource`

## mlblack.conditional.binary_gate

BinaryGate(feature_index: 'int' = 0, threshold: 'float' = 0.0)

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.conditional.primitives import BinaryGate
primitive = BinaryGate(feature_index=0, threshold=1.5)
print(primitive.transform(X))
```

**预期输出：** 返回按样本对齐的门控/hinge特征，不在组件中做训练调度。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.conditional.primitives:BinaryGate`

## mlblack.conditional.soft_gate

SoftGate(feature_index: 'int' = 0, threshold: 'float' = 0.0, temperature: 'float' = 1.0)

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.conditional.primitives import SoftGate
primitive = SoftGate(feature_index=0, threshold=1.5, temperature=0.5)
print(primitive.transform(X))
```

**预期输出：** 返回按样本对齐的门控/hinge特征，不在组件中做训练调度。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.conditional.primitives:SoftGate`

## mlblack.conditional.hinge_feature

HingeFeature(feature_index: 'int' = 0, knot: 'float' = 0.0, side: 'str' = 'right')

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.conditional.primitives import HingeFeature
primitive = HingeFeature(feature_index=0, knot=1.5, side='right')
print(primitive.transform(X))
```

**预期输出：** 返回按样本对齐的门控/hinge特征，不在组件中做训练调度。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.conditional.primitives:HingeFeature`

## mlblack.conditional.one_hot_gate

OneHotGate(feature_index: 'int' = 0, values: 'Sequence[float]' = <factory>)

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.conditional.primitives import OneHotGate
primitive = OneHotGate(feature_index=1, values=(0.,1.))
print(primitive.transform(X))
```

**预期输出：** 返回按样本对齐的门控/hinge特征，不在组件中做训练调度。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.conditional.primitives:OneHotGate`

## mlblack.conditional.conditional / mlblack.conditional.primitives

Auto-discovered mlblack component `conditional.conditional`.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.conditional.primitives import ConditionalPrimitive, BinaryGate
primitive: ConditionalPrimitive = BinaryGate(feature_index=0, threshold=1.5)
print(primitive.transform(X))
```

**预期输出：** 抽象ConditionalPrimitive由BinaryGate具体实现消费；不直接实例化会抛NotImplementedError的基类。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.conditional.primitives:ConditionalPrimitive`, `mlblack.pipeline.conditional.primitives:ConditionalPrimitive`

## mlblack.conditional.conditional_primitive

Declarative conditional primitive used by symbolic grammar lowering.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
from mlblack.pipeline.conditional.primitives import ConditionalPrimitiveSpec
spec = ConditionalPrimitiveSpec(name='gate_a', family='binary_gate', source_features=('a',), parameters={'threshold':1.5})
print(spec.describe())
```

**预期输出：** 保存带来源字段的条件原语描述；Spec不是transform实现，也不会自动训练。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.conditional.primitives:ConditionalPrimitiveSpec`

## mlblack.conditional.composer / mlblack.conditional.primitive_feature_composer

Composes conditional primitives into deterministic feature transforms.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.conditional.composer import PrimitiveFeatureComposer
from mlblack.pipeline.conditional.primitives import BinaryGate, HingeFeature
composer = PrimitiveFeatureComposer(primitives=(BinaryGate(0, 1.5), HingeFeature(0, 1.0)))
print(composer.transform(X))
```

**预期输出：** 原2列后追加2列条件特征，4×4输出；两个Catalog键是同一类型。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.conditional.composer:PrimitiveFeatureComposer`, `mlblack.pipeline.conditional.composer:PrimitiveFeatureComposer`

## mlblack.conditional.route_then_formula_composer

Composable condition descriptor for representation builders.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.conditional.composer import RouteThenFormulaComposer
from mlblack.models.conditional import ThresholdRouter
composer = RouteThenFormulaComposer(router=ThresholdRouter(0, (1.5,)), branch_formulas=('left','right'))
print(composer.route(X))
print(composer.describe())
```

**预期输出：** 返回路由号及分支描述；该对象本身不求解字符串公式、不训练分支。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.conditional.composer:RouteThenFormulaComposer`

## mlblack.conditional.shared_backbone_residual_composer

SharedBackboneResidualComposer(backbone: 'Any', residual_branches: 'Sequence[Any]', router: 'Any | None' = None, metadata: 'Mapping[str, Any]' = <factory>)

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.models.linear import LinearPointModel
base = LinearPointModel(intercept=1., weights=np.array([2., -0.5]))
from mlblack.pipeline.conditional.composer import SharedBackboneResidualComposer
from mlblack.models.conditional import ThresholdRouter
composer = SharedBackboneResidualComposer(backbone=base, residual_branches=(base, base),
    router=ThresholdRouter(0, (1.5,)))
print(composer.predict(X))
```

**预期输出：** 每行基础预测加所选分支残差；分支必须已具备predict，训练归属仍由正式Case决定。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.conditional.composer:SharedBackboneResidualComposer`

## mlblack.symbolic_pipeline.function_pool_pipeline

Symbolic search-space pipeline.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.symbolic.pool_pipeline import FunctionPoolPipeline
space = FunctionPoolPipeline().build(X, y=y, feature_names=('a','b'))
print(space.describe())
```

**预期输出：** 按明确的X/y建立初始函数空间和候选项；不是SolutionPool的候选区域。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.symbolic.pool_pipeline:FunctionPoolPipeline`

## mlblack.symbolic_pipeline.function_pool / mlblack.symbolic_pipeline.candidate_term

Current active symbolic candidate pool.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.symbolic.pool_pipeline import FunctionPoolPipeline
space = FunctionPoolPipeline().build(X, y=y, feature_names=('a','b'))
from mlblack.pipeline.symbolic.function_space import FunctionPool, CandidateTerm
pool: FunctionPool = space.pool
term: CandidateTerm = pool.terms[0]
print(term.values, term.describe())
print(pool.top_by_prior_corr(3).describe())
```

**预期输出：** 读取真实构建的函数项值和按先验相关度选出的最多3项；函数池不是搜索解池。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.symbolic.function_space:FunctionPool`, `mlblack.pipeline.symbolic.function_space:CandidateTerm`

## mlblack.symbolic_pipeline.function_space / mlblack.symbolic_pipeline.function_space_provider

Declarative symbolic search-space plus a materialized active pool.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.symbolic.pool_pipeline import FunctionPoolPipeline
space = FunctionPoolPipeline().build(X, y=y, feature_names=('a','b'))
from mlblack.pipeline.symbolic.function_space import FunctionSpace, FunctionSpaceProvider
provider: FunctionSpaceProvider = FunctionPoolPipeline()
space: FunctionSpace = provider.build(X, y=y, feature_names=('a','b'))
print(space.describe())
```

**预期输出：** FunctionSpaceProvider协议由真实FunctionPoolPipeline实现；空间保留特征名、函数项与注册表摘要。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.symbolic.function_space:FunctionSpace`, `mlblack.pipeline.symbolic.function_space:FunctionSpaceProvider`

## mlblack.symbolic_pipeline.dynamic_function_pool_pipeline

Residual/gradient/budget/gate aware symbolic pool updater.

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.symbolic.pool_pipeline import FunctionPoolPipeline
space = FunctionPoolPipeline().build(X, y=y, feature_names=('a','b'))
from mlblack.pipeline.symbolic.dynamic_pool import DynamicFunctionPoolPipeline
update = DynamicFunctionPoolPipeline().update(X, base_pool=space.pool, y=y, residuals=y-y.mean(),
    budget_remaining_ratio=0.5, feature_names=('a','b'))
print(update.as_dict())
```

**预期输出：** 根据明确残差与预算信号产生动态函数池更新，不替代Adapter的候选接纳。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.symbolic.dynamic_pool:DynamicFunctionPoolPipeline`

## mlblack.symbolic_pipeline.primitive_registry / mlblack.symbolic_pipeline.unary_primitive / mlblack.symbolic_pipeline.pair_grammar_rule

PrimitiveRegistry(unary_specs: 'tuple[UnaryPrimitiveSpec, ...]', pair_rules: 'tuple[PairGrammarRule, ...]')

**输入与前提：** 使用下方公开合成数据；不读取业务文件或启动训练。

**装配位置：** Case的pipeline/或单个语义组件调用处。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.symbolic.primitives import PrimitiveRegistry, UnaryPrimitiveSpec, PairGrammarRule
unary = UnaryPrimitiveSpec(key='identity', activation_family='linear', output_family='raw', complexity=1.,
    build_expr=lambda expr, params: dict(expr), evaluate_values=lambda values, params: values,
    build_name=lambda name, params: str(name))
pair = PairGrammarRule(key='add', activation_family='linear', output_family='sum', complexity=1.,
    build_expr=lambda left,right,params: {'type':'binary','op':'add','left':left,'right':right},
    evaluate_values=lambda left,right,params: left+right, build_name=lambda left,right,params: f'({left}+{right})')
registry = PrimitiveRegistry(unary_specs=(unary,), pair_rules=(pair,))
print(registry.describe())
print(pair.evaluate_values(np.array([1.,2.]), np.array([3.,4.]), {}))
```

**预期输出：** 显式注册一个一元与一个二元原语及其数值语义；正式grammar的回调参数须与builder协议匹配。

**依赖与边界：** NumPy与统一三仓环境。

**接口依据：** `mlblack.pipeline.symbolic.primitives:PrimitiveRegistry`, `mlblack.pipeline.symbolic.primitives:UnaryPrimitiveSpec`, `mlblack.pipeline.symbolic.primitives:PairGrammarRule`

## mlblack.preset.mlp_regression

ML 词汇入口：optimizer=sgd/adam/adamw 内部解析为 nsgablack 通用梯度 Adapter 与 mlblack Torch Evaluation Provider。

**输入与前提：** 在正式Case的build_solver中准备下方形状的数据；本片段只演示装配，不开训练循环。

**装配位置：** examples/cases/<project>/cases/<case>/build_solver.py，返回trainer作为canonical build_solver结果。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.data_views.numeric import NumericDataView
data = NumericDataView(X_train=X, y_train=y, feature_names=('a', 'b'))
from mlblack.presets.neural import build_mlp_regression_trainer
# 位于正式Case的build_solver内；返回后由Project绑定资源。
trainer = build_mlp_regression_trainer(data, hidden_layers=(4,), learning_rate=0.001)
# 将trainer返回给Case runner；不要在Catalog浏览时调用fit。
print(type(trainer).__name__)
```

**预期输出：** 得到已装配LearningSolver门面；实际fit、资源授权、检查点与结果发布由正式Case/Project运行。

**依赖与边界：** NumPy及三仓；neural/temporal/tabnet预设实际求值还需对应Torch Provider，L0设备授权由Project提供。

**接口依据：** `mlblack.presets.neural:build_mlp_regression_trainer`

## mlblack.preset.arima_sarimax_forecast

ARIMA/SARIMAX 规格由 Codec 解码，并在 LearningSolver 生命周期内由 TimeSeries Problem/Provider 拟合。

**输入与前提：** 在正式Case的build_solver中准备下方形状的数据；本片段只演示装配，不开训练循环。

**装配位置：** examples/cases/<project>/cases/<case>/build_solver.py，返回trainer作为canonical build_solver结果。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.presets.time_series import build_arima_sarimax_forecast_trainer
# 位于正式Case的build_solver内；返回后由Project绑定资源。
trainer = build_arima_sarimax_forecast_trainer(series, order=(1,0,0), backend='numpy_fallback')
# 将trainer返回给Case runner；不要在Catalog浏览时调用fit。
print(type(trainer).__name__)
```

**预期输出：** 得到已装配LearningSolver门面；实际fit、资源授权、检查点与结果发布由正式Case/Project运行。

**依赖与边界：** NumPy及三仓；neural/temporal/tabnet预设实际求值还需对应Torch Provider，L0设备授权由Project提供。

**接口依据：** `mlblack.presets.time_series:build_arima_sarimax_forecast_trainer`

## mlblack.preset.baseline_forecast_search

对 naive/季节性-naive/移动平均预测策略进行随机搜索。

**输入与前提：** 在正式Case的build_solver中准备下方形状的数据；本片段只演示装配，不开训练循环。

**装配位置：** examples/cases/<project>/cases/<case>/build_solver.py，返回trainer作为canonical build_solver结果。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.presets.time_series import build_baseline_forecast_search_trainer
# 位于正式Case的build_solver内；返回后由Project绑定资源。
trainer = build_baseline_forecast_search_trainer(series, population_size=4)
# 将trainer返回给Case runner；不要在Catalog浏览时调用fit。
print(type(trainer).__name__)
```

**预期输出：** 得到已装配LearningSolver门面；实际fit、资源授权、检查点与结果发布由正式Case/Project运行。

**依赖与边界：** NumPy及三仓；neural/temporal/tabnet预设实际求值还需对应Torch Provider，L0设备授权由Project提供。

**接口依据：** `mlblack.presets.time_series:build_baseline_forecast_search_trainer`

## mlblack.preset.linear_autoregressive_forecast

线性自回归拟合规格由 Codec 解码，闭式拟合在 LearningSolver 的 TimeSeries Problem 边界执行。

**输入与前提：** 在正式Case的build_solver中准备下方形状的数据；本片段只演示装配，不开训练循环。

**装配位置：** examples/cases/<project>/cases/<case>/build_solver.py，返回trainer作为canonical build_solver结果。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.presets.time_series import build_linear_autoregressive_forecast_trainer
# 位于正式Case的build_solver内；返回后由Project绑定资源。
trainer = build_linear_autoregressive_forecast_trainer(series, lags=(1,2), ridge=1e-6)
# 将trainer返回给Case runner；不要在Catalog浏览时调用fit。
print(type(trainer).__name__)
```

**预期输出：** 得到已装配LearningSolver门面；实际fit、资源授权、检查点与结果发布由正式Case/Project运行。

**依赖与边界：** NumPy及三仓；neural/temporal/tabnet预设实际求值还需对应Torch Provider，L0设备授权由Project提供。

**接口依据：** `mlblack.presets.time_series:build_linear_autoregressive_forecast_trainer`

## mlblack.preset.orthogonal_logistic_classification

Orthogonal linear logits with binary probability head and classification metrics.

**输入与前提：** 在正式Case的build_solver中准备下方形状的数据；本片段只演示装配，不开训练循环。

**装配位置：** examples/cases/<project>/cases/<case>/build_solver.py，返回trainer作为canonical build_solver结果。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.data_views.numeric import NumericDataView
data = NumericDataView(X_train=X, y_train=np.array([0,1,0,1]), feature_names=('a', 'b'))
from mlblack.presets.classification import build_orthogonal_logistic_classification_trainer
# 位于正式Case的build_solver内；返回后由Project绑定资源。
trainer = build_orthogonal_logistic_classification_trainer(data, population_size=4)
# 将trainer返回给Case runner；不要在Catalog浏览时调用fit。
print(type(trainer).__name__)
```

**预期输出：** 得到已装配LearningSolver门面；实际fit、资源授权、检查点与结果发布由正式Case/Project运行。

**依赖与边界：** NumPy及三仓；neural/temporal/tabnet预设实际求值还需对应Torch Provider，L0设备授权由Project提供。

**接口依据：** `mlblack.presets.classification:build_orthogonal_logistic_classification_trainer`

## mlblack.preset.tabular_tabnet_classification

TabNet 表格分类预设：TabularNeuralClassificationProblem 定义交叉熵/指标，TorchEvaluationProvider 执行 autograd，nsgablack GradientOptimizerAdapter 执行稳定优化方法。

**输入与前提：** 在正式Case的build_solver中准备下方形状的数据；本片段只演示装配，不开训练循环。

**装配位置：** examples/cases/<project>/cases/<case>/build_solver.py，返回trainer作为canonical build_solver结果。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.data_views.numeric import NumericDataView
data = NumericDataView(X_train=X, y_train=np.array([0,1,0,1]), feature_names=('a', 'b'))
from mlblack.presets.neural import build_tabular_tabnet_classification_trainer
# 位于正式Case的build_solver内；返回后由Project绑定资源。
trainer = build_tabular_tabnet_classification_trainer(data, hidden_dim=8, n_steps=2, learning_rate=0.001)
# 将trainer返回给Case runner；不要在Catalog浏览时调用fit。
print(type(trainer).__name__)
```

**预期输出：** 得到已装配LearningSolver门面；实际fit、资源授权、检查点与结果发布由正式Case/Project运行。

**依赖与边界：** NumPy及三仓；neural/temporal/tabnet预设实际求值还需对应Torch Provider，L0设备授权由Project提供。

**接口依据：** `mlblack.presets.neural:build_tabular_tabnet_classification_trainer`

## mlblack.preset.tabular_tabnet_regression

TabNet 表格回归预设：TabularNeuralRegressionProblem 定义 MSE/指标，TorchEvaluationProvider 执行 autograd，nsgablack GradientOptimizerAdapter 执行稳定优化方法。

**输入与前提：** 在正式Case的build_solver中准备下方形状的数据；本片段只演示装配，不开训练循环。

**装配位置：** examples/cases/<project>/cases/<case>/build_solver.py，返回trainer作为canonical build_solver结果。

**最小调用：**

```python
import numpy as np
X = np.array([[0., 1.], [1., 0.], [2., 1.], [3., 0.]])
y = np.array([1., 2., 5., 6.])
from mlblack.pipeline.data_views.numeric import NumericDataView
data = NumericDataView(X_train=X, y_train=y, feature_names=('a', 'b'))
from mlblack.presets.neural import build_tabular_tabnet_regression_trainer
# 位于正式Case的build_solver内；返回后由Project绑定资源。
trainer = build_tabular_tabnet_regression_trainer(data, hidden_dim=8, n_steps=2, learning_rate=0.001)
# 将trainer返回给Case runner；不要在Catalog浏览时调用fit。
print(type(trainer).__name__)
```

**预期输出：** 得到已装配LearningSolver门面；实际fit、资源授权、检查点与结果发布由正式Case/Project运行。

**依赖与边界：** NumPy及三仓；neural/temporal/tabnet预设实际求值还需对应Torch Provider，L0设备授权由Project提供。

**接口依据：** `mlblack.presets.neural:build_tabular_tabnet_regression_trainer`

## mlblack.preset.temporal_deepar_forecast

DeepAR 风格概率预测预设：LSTM 主干输出高斯分布参数，经 ML Problem + TorchEvaluationProvider + nsgablack GradientOptimizerAdapter 训练。

**输入与前提：** 在正式Case的build_solver中准备下方形状的数据；本片段只演示装配，不开训练循环。

**装配位置：** examples/cases/<project>/cases/<case>/build_solver.py，返回trainer作为canonical build_solver结果。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.pipeline.time_series import TimeSeriesWindowConfig, TimeSeriesWindowingComponent
windowing = TimeSeriesWindowingComponent(TimeSeriesWindowConfig(
    lags=tuple(range(1,13)), horizon=1, format='sequence', valid_size=0.2))
data, _ = windowing.fit_transform(series)
from mlblack.presets.neural import build_temporal_deepar_forecast_trainer
# 位于正式Case的build_solver内；返回后由Project绑定资源。
trainer = build_temporal_deepar_forecast_trainer(data, input_dim=1, sequence_length=12, hidden_dim=8, learning_rate=0.001)
# 将trainer返回给Case runner；不要在Catalog浏览时调用fit。
print(type(trainer).__name__)
```

**预期输出：** 得到已装配LearningSolver门面；实际fit、资源授权、检查点与结果发布由正式Case/Project运行。

**依赖与边界：** NumPy及三仓；neural/temporal/tabnet预设实际求值还需对应Torch Provider，L0设备授权由Project提供。

**接口依据：** `mlblack.presets.neural:build_temporal_deepar_forecast_trainer`

## mlblack.preset.temporal_lstm_forecast

LSTM 神经序列预测预设，经 Temporal Problem + TorchEvaluationProvider + nsgablack GradientOptimizerAdapter 训练。

**输入与前提：** 在正式Case的build_solver中准备下方形状的数据；本片段只演示装配，不开训练循环。

**装配位置：** examples/cases/<project>/cases/<case>/build_solver.py，返回trainer作为canonical build_solver结果。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.pipeline.time_series import TimeSeriesWindowConfig, TimeSeriesWindowingComponent
windowing = TimeSeriesWindowingComponent(TimeSeriesWindowConfig(
    lags=tuple(range(1,13)), horizon=1, format='sequence', valid_size=0.2))
data, _ = windowing.fit_transform(series)
from mlblack.presets.neural import build_temporal_lstm_forecast_trainer
# 位于正式Case的build_solver内；返回后由Project绑定资源。
trainer = build_temporal_lstm_forecast_trainer(data, input_dim=1, sequence_length=12, hidden_dim=8, learning_rate=0.001)
# 将trainer返回给Case runner；不要在Catalog浏览时调用fit。
print(type(trainer).__name__)
```

**预期输出：** 得到已装配LearningSolver门面；实际fit、资源授权、检查点与结果发布由正式Case/Project运行。

**依赖与边界：** NumPy及三仓；neural/temporal/tabnet预设实际求值还需对应Torch Provider，L0设备授权由Project提供。

**接口依据：** `mlblack.presets.neural:build_temporal_lstm_forecast_trainer`

## mlblack.preset.temporal_nbeats_forecast

N-BEATS 风格堆叠残差块预测预设，经 ML Problem + TorchEvaluationProvider + nsgablack GradientOptimizerAdapter 训练。

**输入与前提：** 在正式Case的build_solver中准备下方形状的数据；本片段只演示装配，不开训练循环。

**装配位置：** examples/cases/<project>/cases/<case>/build_solver.py，返回trainer作为canonical build_solver结果。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.pipeline.time_series import TimeSeriesWindowConfig, TimeSeriesWindowingComponent
windowing = TimeSeriesWindowingComponent(TimeSeriesWindowConfig(
    lags=tuple(range(1,13)), horizon=1, format='sequence', valid_size=0.2))
data, _ = windowing.fit_transform(series)
from mlblack.presets.neural import build_temporal_nbeats_forecast_trainer
# 位于正式Case的build_solver内；返回后由Project绑定资源。
trainer = build_temporal_nbeats_forecast_trainer(data, input_dim=1, sequence_length=12, hidden_dim=8, learning_rate=0.001)
# 将trainer返回给Case runner；不要在Catalog浏览时调用fit。
print(type(trainer).__name__)
```

**预期输出：** 得到已装配LearningSolver门面；实际fit、资源授权、检查点与结果发布由正式Case/Project运行。

**依赖与边界：** NumPy及三仓；neural/temporal/tabnet预设实际求值还需对应Torch Provider，L0设备授权由Project提供。

**接口依据：** `mlblack.presets.neural:build_temporal_nbeats_forecast_trainer`

## mlblack.preset.temporal_patchtst_forecast

PatchTST 补丁嵌入 + Transformer 编码器预测预设，经 ML Problem + TorchEvaluationProvider + nsgablack GradientOptimizerAdapter 训练。

**输入与前提：** 在正式Case的build_solver中准备下方形状的数据；本片段只演示装配，不开训练循环。

**装配位置：** examples/cases/<project>/cases/<case>/build_solver.py，返回trainer作为canonical build_solver结果。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.pipeline.time_series import TimeSeriesWindowConfig, TimeSeriesWindowingComponent
windowing = TimeSeriesWindowingComponent(TimeSeriesWindowConfig(
    lags=tuple(range(1,13)), horizon=1, format='sequence', valid_size=0.2))
data, _ = windowing.fit_transform(series)
from mlblack.presets.neural import build_temporal_patchtst_forecast_trainer
# 位于正式Case的build_solver内；返回后由Project绑定资源。
trainer = build_temporal_patchtst_forecast_trainer(data, input_dim=1, sequence_length=12, hidden_dim=8, learning_rate=0.001)
# 将trainer返回给Case runner；不要在Catalog浏览时调用fit。
print(type(trainer).__name__)
```

**预期输出：** 得到已装配LearningSolver门面；实际fit、资源授权、检查点与结果发布由正式Case/Project运行。

**依赖与边界：** NumPy及三仓；neural/temporal/tabnet预设实际求值还需对应Torch Provider，L0设备授权由Project提供。

**接口依据：** `mlblack.presets.neural:build_temporal_patchtst_forecast_trainer`

## mlblack.preset.temporal_tcn_forecast

TCN 神经序列预测预设，经 Temporal Problem + TorchEvaluationProvider + nsgablack GradientOptimizerAdapter 训练。

**输入与前提：** 在正式Case的build_solver中准备下方形状的数据；本片段只演示装配，不开训练循环。

**装配位置：** examples/cases/<project>/cases/<case>/build_solver.py，返回trainer作为canonical build_solver结果。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.pipeline.time_series import TimeSeriesWindowConfig, TimeSeriesWindowingComponent
windowing = TimeSeriesWindowingComponent(TimeSeriesWindowConfig(
    lags=tuple(range(1,13)), horizon=1, format='sequence', valid_size=0.2))
data, _ = windowing.fit_transform(series)
from mlblack.presets.neural import build_temporal_tcn_forecast_trainer
# 位于正式Case的build_solver内；返回后由Project绑定资源。
trainer = build_temporal_tcn_forecast_trainer(data, input_dim=1, sequence_length=12, channels=(4,), learning_rate=0.001)
# 将trainer返回给Case runner；不要在Catalog浏览时调用fit。
print(type(trainer).__name__)
```

**预期输出：** 得到已装配LearningSolver门面；实际fit、资源授权、检查点与结果发布由正式Case/Project运行。

**依赖与边界：** NumPy及三仓；neural/temporal/tabnet预设实际求值还需对应Torch Provider，L0设备授权由Project提供。

**接口依据：** `mlblack.presets.neural:build_temporal_tcn_forecast_trainer`

## mlblack.preset.temporal_tft_forecast

Temporal Fusion Transformer 预测预设，含门控残差网络和可解释多头自注意力，经统一 Problem/Provider/GradientOptimizer 路径训练。

**输入与前提：** 在正式Case的build_solver中准备下方形状的数据；本片段只演示装配，不开训练循环。

**装配位置：** examples/cases/<project>/cases/<case>/build_solver.py，返回trainer作为canonical build_solver结果。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.pipeline.time_series import TimeSeriesWindowConfig, TimeSeriesWindowingComponent
windowing = TimeSeriesWindowingComponent(TimeSeriesWindowConfig(
    lags=tuple(range(1,13)), horizon=1, format='sequence', valid_size=0.2))
data, _ = windowing.fit_transform(series)
from mlblack.presets.neural import build_temporal_tft_forecast_trainer
# 位于正式Case的build_solver内；返回后由Project绑定资源。
trainer = build_temporal_tft_forecast_trainer(data, input_dim=1, sequence_length=12, hidden_dim=8, learning_rate=0.001)
# 将trainer返回给Case runner；不要在Catalog浏览时调用fit。
print(type(trainer).__name__)
```

**预期输出：** 得到已装配LearningSolver门面；实际fit、资源授权、检查点与结果发布由正式Case/Project运行。

**依赖与边界：** NumPy及三仓；neural/temporal/tabnet预设实际求值还需对应Torch Provider，L0设备授权由Project提供。

**接口依据：** `mlblack.presets.neural:build_temporal_tft_forecast_trainer`

## mlblack.preset.temporal_transformer_forecast

Transformer 神经序列预测预设，经 Temporal Problem + TorchEvaluationProvider + nsgablack GradientOptimizerAdapter 训练。

**输入与前提：** 在正式Case的build_solver中准备下方形状的数据；本片段只演示装配，不开训练循环。

**装配位置：** examples/cases/<project>/cases/<case>/build_solver.py，返回trainer作为canonical build_solver结果。

**最小调用：**

```python
import numpy as np
from mlblack.pipeline.data_views.time_series import TimeSeriesDataView
series = TimeSeriesDataView(y=np.arange(60, dtype=float) + np.sin(np.arange(60)))
from mlblack.pipeline.time_series import TimeSeriesWindowConfig, TimeSeriesWindowingComponent
windowing = TimeSeriesWindowingComponent(TimeSeriesWindowConfig(
    lags=tuple(range(1,13)), horizon=1, format='sequence', valid_size=0.2))
data, _ = windowing.fit_transform(series)
from mlblack.presets.neural import build_temporal_transformer_forecast_trainer
# 位于正式Case的build_solver内；返回后由Project绑定资源。
trainer = build_temporal_transformer_forecast_trainer(data, input_dim=1, sequence_length=12, hidden_dim=8, learning_rate=0.001)
# 将trainer返回给Case runner；不要在Catalog浏览时调用fit。
print(type(trainer).__name__)
```

**预期输出：** 得到已装配LearningSolver门面；实际fit、资源授权、检查点与结果发布由正式Case/Project运行。

**依赖与边界：** NumPy及三仓；neural/temporal/tabnet预设实际求值还需对应Torch Provider，L0设备授权由Project提供。

**接口依据：** `mlblack.presets.neural:build_temporal_transformer_forecast_trainer`
