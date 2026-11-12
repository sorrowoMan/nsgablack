# ML 数据管线应用：先定数据含义，再交给模型和搜索

三个例子各用 `mlblack/examples/cases/catalog_codec_demo/` 的独立完整副本，保留 Project L0、默认单个 `linear_point` Case、规范运行入口和别名。路径相对副本根目录；代码是完整文件替换，不在原 Project 上依次叠加三个例子。本页只做源码与语法核对，未运行训练、模型、数据库或网络请求，也没有生成运行收据。

## mlblack.pipeline.data_pipeline_chain · 从混合行到可复用的数值准备链

**什么时候用：** 原始记录同时含数值、类别、布尔值和字符串标签，要把“如何数值化、保留哪些列、怎样缩放”固定下来，供训练和以后同口径推理使用。这里实际消费 DefaultNumericizer/TargetCodec、DataPipeline、DataPipelineComponent、IdentityComponent、SelectColumnsComponent、ZScoreNormalizeComponent。两个 DefaultNumericizer 目录键指同一实现，不需要装两次。

**先准备什么：** 当前三仓与 NumPy；使用完整 catalog_codec_demo 副本，保留 Project 配置和规范入口。12 条训练记录、6 条独立验证记录，两类别设备 A/B，标签固定 off/on。先划分再拟合特征词表和缩放状态，不将验证记录拼入 fit。

**放在哪：** 完整替换 `cases/linear_point/config.py`、`pipeline/main.py`、`problem/__init__.py`、`adapter/__init__.py`、`build_solver.py`；保留原 pipeline 包导出 build_pipeline。Project 根新增 `run_prepared_and_report.py`。

**接入步骤：** SelectColumns 使用数值化后的列位置，不能直接拿原始 schema 的列号代替展开后的 one-hot 位置。

```python
# cases/linear_point/config.py
NORMALIZE = True
```

```python
# cases/linear_point/pipeline/main.py
import numpy as np
from mlblack.assembly.schema import DatasetSchema, FeatureSpec, TargetSpec
from mlblack.pipeline import (DataPipeline, DataPipelineComponent, IdentityComponent,
    SelectColumnsComponent, ZScoreNormalizeComponent, NumericDataView)
from mlblack.pipeline.numericizer import DefaultNumericizer, NumericizationPlan, TargetCodec

class RequireFinite(DataPipelineComponent):
    name = "require_finite"
    def transform(self, data, state=None, context=None):
        for X in (data.X_train, data.X_valid):
            if X is not None and not np.all(np.isfinite(X)):
                raise ValueError("features must be finite before normalization")
        return data

def build_pipeline(normalize=True):
    target = TargetCodec(kind="classification", classes=("off", "on"))
    def rows(count, offset):
        return [{"temperature": float(i+offset), "pressure": 2.+.1*i,
            "device": "A" if i % 2 == 0 else "B", "enabled": bool(i % 3),
            "label": "on" if (i+offset) % 3 == 0 else "off"}
            for i in range(count)]
    train, valid = rows(12, 0), rows(6, 20)
    def encoded(items):
        labels = target.encode([row["label"] for row in items])
        return [{**row, "label": float(label)} for row, label in zip(items, labels)]
    schema = DatasetSchema(features=(FeatureSpec("temperature"), FeatureSpec("pressure"),
        FeatureSpec("device", dtype="category"), FeatureSpec("enabled", dtype="bool")),
        targets=(TargetSpec("label"),))
    numericizer = DefaultNumericizer(NumericizationPlan.from_schema(schema)).fit(encoded(train))
    allowed = {str(c.metadata["value"]) for c in numericizer.plan.columns
               if c.source_key == "device" and c.kind == "onehot"}
    if any(row["device"] not in allowed for row in valid):
        raise ValueError("validation has an unseen device; choose a policy explicitly")
    t, v = numericizer.transform(encoded(train)), numericizer.transform(encoded(valid))
    raw = NumericDataView(X_train=t.X_train, y_train=t.y_train,
        X_valid=v.X_train, y_valid=v.y_train, feature_names=t.feature_names)
    components = [IdentityComponent(), RequireFinite(), SelectColumnsComponent(columns=(0, 1, 2, 3))]
    if normalize:
        components.append(ZScoreNormalizeComponent())
    preparation = DataPipeline(components, name="tabular_preparation")
    data = preparation.fit_transform(raw)
    blueprint = {"numericization": numericizer.plan.as_dict(), "target": target.as_dict(),
        "pipeline": preparation.describe(), "output_columns": list(data.effective_feature_names)}
    return data, blueprint
```

DefaultNumericizer 本身直接 `float(target)`，**不会自动调用 TargetCodec**；所以本例先编码标签。设备词表只从训练记录产生；未见设备会按默认 one-hot 得到全零，schema 的 unknown="error" 不会在此实现里自动执行，因此示例显式拒绝。接入真实数据还要检查缺字段、类型、词表，不把 schema 声明当完整验证器。

原始数值列顺序是 temperature、pressure、device=A、device=B、enabled；选择前四列丢掉 enabled。ZScore 的 mean/std 只由 X_train 拟合，同一状态同时变换验证数据，标签不变；常数列 std 用 1。RequireFinite 是实际加入链的自定义 DataPipelineComponent，不是只写了一个未被消费的类。

```python
# cases/linear_point/problem/__init__.py
from dataclasses import replace
from mlblack.problems import SupervisedClassificationProblem

class PreparedClassification(SupervisedClassificationProblem):
    def __init__(self, data, blueprint):
        super().__init__(data, objective_metrics=("log_loss",), use_valid_objective=False)
        self.blueprint = blueprint
    def evaluate(self, model, state, context):
        feedback = super().evaluate(model, state, context)
        return replace(feedback, signals={**dict(feedback.signals),
            "prepared_columns": tuple(self.data.effective_feature_names),
            "prepared_train_rows": len(self.data.y_train)})
    def build_model_artifact(self, model, context):
        return {"schema": "case.prepared_binary_classifier/v1",
            "preparation": self.blueprint, "classes": list(model.classes_),
            "temperature": model.temperature, "threshold": model.threshold,
            "logit": model.logit_model.as_dict()}

def build_problem(data, blueprint):
    return PreparedClassification(data, blueprint)
```

```python
# cases/linear_point/adapter/__init__.py
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter

def build_adapter():
    return build_optimization_adapter("search.random_gaussian", population_size=6,
        mutation_scale=.2, random_seed=17, objective_aggregation="first")
```

## prepared_pipeline_wiring · 准备链的装配、结果与变体

这是上一节的连续接线，仍属于同一份独立 Project；先保存上方数据、Problem 和 Adapter，再保存以下 builder 和薄报告入口。

```python
# cases/linear_point/build_solver.py
from mlblack.integrations.nsgablack_control import build_learning_solver
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations.heads import BinaryLogisticHead
from nsgablack.project import apply_solver_component_overrides
from .config import NORMALIZE
from .pipeline.main import build_pipeline
from .problem import build_problem
from .adapter import build_adapter

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("this recipe uses the declared preparation and budget")
    data, blueprint = build_pipeline(NORMALIZE)
    representation = LinearPointRepresentation(LinearPointConfig(n_features=data.n_features,
        feature_names=data.effective_feature_names, random_seed=17),
        head=BinaryLogisticHead(classes=(0, 1)))
    solver = build_learning_solver(problem=build_problem(data, blueprint),
        representation=representation, adapter=build_adapter(), compute_backend="numpy",
        resource_context=resource_context, run_name="prepared_classifier")
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(6)
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

```python
# run_prepared_and_report.py
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
    if value.best_feedback is None:
        raise ValueError("no evaluated prepared-model feedback")
    payload = {"run_id": run.run_id, "objectives": value.best_objectives.tolist(),
        "metrics": dict(value.best_feedback.metrics), "signals": dict(value.best_feedback.signals),
        "model_ref": None if value.best_model_ref is None else value.best_model_ref.as_dict()}
    path = root / "results" / "prepared.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

**怎样判断接对：** 本次 prepared.json 的 signals 应列出四个准备后列名与12行训练，单目标等于 train.log_loss，验证指标单列，不要求验证缩放后的均值为零。候选是五参数二分类 logit；最终 Artifact 蓝图包含训练词表、TargetCodec classes、选列规则、真实 mean/std 与模型块，不把模型系数误当原始单位系数。这是本 Case 蓝图，没有自动通用加载器；恢复/推理时不能重新用待预测数据 fit。Identity 只保留输入，不额外复制、求值或训练。

**运行入口：** 副本根先执行 `python run_project.py --check --build-check`，然后只执行一次 `python run_prepared_and_report.py`。后者通过正式 Project 获得 L0、运行并读取 TrainerResult/模型引用，不另写训练循环。旧报告和静态核对不构成运行证明。

### 变体一：保留数值化和选列，只移除缩放

**目的：** 比较缩放对搜索条件的影响，保留类别编码和完整数据契约。

**改在哪里：** 完整替换配置，其余文件已有真实分支。

```python
# cases/linear_point/config.py
NORMALIZE = False
```

**行为变化：** DataPipeline 不再加入 ZScore；输出仍四列，Artifact 不再声称有缩放状态。Identity、有限性检查、选列和词表都保留。

**限制：** 同一步长现在作用于不同单位，不能据此保证同等搜索效果。DataPipeline 按 component.name 存 fit state，同名有状态组件会覆盖条目；需要重复缩放时先给组件稳定不同名称，不能复制两个同名 ZScore 后假定 transform 能恢复各自状态。

源码：`mlblack/pipeline/base.py`、`components.py`、`numericizer/default.py`、`numericizer/plan.py`、`numericizer/target_codec.py`、`problems/classification.py`、`core/artifact_provider.py`。

## mlblack.pipeline.time_series_windowing · 把已观测历史变成一步回归行

**什么时候用：** 已有按时间排列的一元序列，要把已观测历史转为 lag 特征，再交给普通表格模型。配套 `mlblack.pipeline.time_series_window` 是 TimeSeriesWindowConfig，不是另一个执行组件或别名函数。本节演示 flat、horizon=1。

**先准备什么：** 当前三仓与 NumPy；使用 catalog_codec_demo 另一份完整副本，保留默认 Project/L0/Case。24 个按 t=0…23 排列的合成观测，不随机打乱。主例 lag=(1,2)，最后6个窗口作验证；验证是按到达时刻已知历史进行一步预测，不能当从一个截点递推六步的结果。

**放在哪：** 完整替换 Case 的 config.py、pipeline/main.py、problem/__init__.py、adapter/__init__.py、build_solver.py；保留原 pipeline 包导出。新增 Project 根 run_window_and_report.py。

**接入步骤：** 每一行在 origin=t，用 lag_1=y[t]、lag_2=y[t-1] 预测 y[t+1]，不要把 lag_1 错向后移一位。

```python
# cases/linear_point/config.py
LAGS = (1, 2)
```

```python
# cases/linear_point/pipeline/main.py
import numpy as np
from mlblack.pipeline import TimeSeriesDataView, TimeSeriesWindowConfig, TimeSeriesWindowingComponent

def build_pipeline(lags):
    t = np.arange(24, dtype=float)
    series = TimeSeriesDataView(y=.1*t + np.sin(t/3.),
        time_index=tuple(range(24)), target_name="observed", frequency="D")
    window = TimeSeriesWindowingComponent(TimeSeriesWindowConfig(lags=lags,
        horizon=1, valid_size=6, include_exogenous=False, include_origin_index=False,
        format="flat"))
    data, fitted = window.fit_transform(series)
    return data, {"window": window.describe(), "fit": dict(fitted),
        "origins": list(data.metadata["time_series.origin_indices"]),
        "targets": list(data.metadata["time_series.target_indices"])}
```

窗口组件不训练模型、不产生随机数据；fit 返回窗口描述与规模，transform 依照同一配置重新构造窗口。主例总窗口22行：训练16、验证6，特征数2；第一行使用 y[1]/y[0]，目标 y[2]，最后一行目标 y[23]。验证较后行会使用较早验证期已经观测到的真实值，符合本节明确的一步滚动使用，不符合开放式多步预测。

```python
# cases/linear_point/problem/__init__.py
from dataclasses import replace
from mlblack.problems import SupervisedRegressionProblem

class WindowProblem(SupervisedRegressionProblem):
    def __init__(self, data, blueprint):
        super().__init__(data, use_valid_objective=False)
        self.blueprint = blueprint
    def evaluate(self, model, state, context):
        feedback = super().evaluate(model, state, context)
        return replace(feedback, signals={**dict(feedback.signals),
            "window_features": tuple(self.data.effective_feature_names),
            "window_train_rows": len(self.data.y_train),
            "window_valid_rows": len(self.data.y_valid)})
    def build_model_artifact(self, model, context):
        return {"schema": "case.lagged_linear/v1", "preparation": self.blueprint,
                "linear_model": model.as_dict()}

def build_problem(data, blueprint):
    return WindowProblem(data, blueprint)
```

```python
# cases/linear_point/adapter/__init__.py
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter

def build_adapter():
    return build_optimization_adapter("search.random_gaussian", population_size=6,
        mutation_scale=.2, random_seed=17, objective_aggregation="first")
```

```python
# cases/linear_point/build_solver.py
from mlblack.integrations.nsgablack_control import build_learning_solver
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from nsgablack.project import apply_solver_component_overrides
from .config import LAGS
from .pipeline.main import build_pipeline
from .problem import build_problem
from .adapter import build_adapter

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("this recipe uses its declared window and budget")
    data, blueprint = build_pipeline(LAGS)
    representation = LinearPointRepresentation(LinearPointConfig(n_features=data.n_features,
        feature_names=data.effective_feature_names, random_seed=17))
    solver = build_learning_solver(problem=build_problem(data, blueprint),
        representation=representation, adapter=build_adapter(), compute_backend="numpy",
        resource_context=resource_context, run_name="lagged_linear")
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(6)
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

```python
# run_window_and_report.py
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
    if value.best_feedback is None:
        raise ValueError("no evaluated window-model feedback")
    payload = {"run_id": run.run_id, "objectives": value.best_objectives.tolist(),
        "metrics": dict(value.best_feedback.metrics), "signals": dict(value.best_feedback.signals),
        "model_ref": None if value.best_model_ref is None else value.best_model_ref.as_dict()}
    path = root / "results" / "window.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

**怎样判断接对：** 新 window.json 的 signals 说明 lag 名称与16/6行；objectives 是 `[train.mse,0]`，valid.mse 只观察。Artifact 保存窗口配置、origin/target 坐标及已评估的线性参数，不把未来真值当永久可用输入。这里输出仍是 LinearPointModel，不是自动实现 forecast(n) 的时序模型；上线下一步预测要按同一 lag 顺序提供已经观测到的输入。

**运行入口：** 在副本根先执行 `python run_project.py --check --build-check`，再执行 `python run_window_and_report.py`。后一条只运行一次正式 Project 并读取 TrainerResult；检查正式运行状态及新 run_id，不靠历史 JSON 判断成功。本轮未执行。

### 变体一：加入第四阶历史，仍保持一步目标

**目的：** 引入更远历史，改变特征集合而不改变验证期长度或偷换成多步任务。

**改在哪里：** 完整替换 Case 配置，其他文件都通过同一 LAGS 构建模型和蓝图。

```python
# cases/linear_point/config.py
LAGS = (1, 2, 4)
```

**行为变化：** 特征为 lag_1/lag_2/lag_4，最大 lag=4，窗口20行、训练14/验证6，线性模型从3参数变成4参数，第一目标仍训练 MSE。

**限制：** 不能恢复旧参数布局的 checkpoint。本例不支持直接把 horizon 改成3：当前普通 NumericDataView 的 y 是一维，窗口的多步矩阵会被一维转换打平，不能假称已接上多输出回归。sequence 路由也有专门元数据/模型消费者，不能仅改字符串就声称时序网络已装配；本例始终 flat。原始时间顺序、缺值、外生变量可知时点仍由问题数据层负责。

源码：`mlblack/pipeline/time_series.py::TimeSeriesWindowConfig/TimeSeriesWindowingComponent/build_lagged_numeric_view`、`pipeline/data_views/time_series.py`、`pipeline/data_views/numeric.py`、`problems/supervised.py`。

## mlblack.pipeline.numeric_batch_schedule · batch 切片和训练游标的真实消费者

**什么时候用：** 小批训练需要可恢复的 epoch/cursor，而不是每次读取永远重复第一批。NumericBatchLoader 提供有限切片迭代，NumericBatchSchedule 提供按需下一批；两者都不拥有优化生命周期。本例让 Schedule 真正进入 Torch Evaluation Provider，不把“创建了 schedule 对象”当已启用。

**先准备什么：** 使用 catalog_codec_demo 第三份独立副本；当前三仓、NumPy，以及可选依赖 torch>=2.0 的可用 CPU 安装。保留原 Project 的 CPU/1线程 L0。不下载模型或数据。八行训练、四行验证、一个特征，batch_size=3；Loader 的末批允许不足三行。

**放在哪：** 完整替换 Case 的 config.py、pipeline/main.py、problem/__init__.py、build_solver.py。原 adapter 目录可保留，但本例 builder 显式调用正规 build_gradient_trainer，不再调用旧 adapter 工厂。Project 根新建 run_batch_and_report.py。

**接入步骤：** Loader 用来核对有限训练切片，Schedule 独立创建给 Provider；不预先调用真实 schedule.next_train 来“预览”，避免提前消费游标。

```python
# cases/linear_point/config.py
BATCH_SIZE = 3
```

```python
# cases/linear_point/pipeline/main.py
import numpy as np
from mlblack.pipeline import NumericDataView, DatasetStreamConfig, NumericBatchLoader

def build_pipeline(batch_size):
    X = np.linspace(-1., 1., 8).reshape(-1, 1)
    V = np.array([[-.9], [-.2], [.3], [.8]])
    data = NumericDataView(X_train=X, y_train=1.+2.*X[:, 0],
        X_valid=V, y_valid=1.+2.*V[:, 0], feature_names=("x",))
    config = DatasetStreamConfig(batch_size=int(batch_size), shuffle=False,
        drop_last=False, repeat=1, seed=17)
    batches = tuple(NumericBatchLoader(data, config).iter_train())
    covered = tuple(index for batch in batches for index in batch.indices)
    if covered != tuple(range(8)):
        raise ValueError("the declared finite loader must cover every training row once")
    return data, config
```

Loader 这里实际被调用，不参与梯度顺序：配置下切片大小为3/3/2，indices 是原 DataView 行位置。每次重新调用 iter_train 都从配置种子重新开始；它不是持久训练游标，也不是从磁盘流式读取。iter_valid 同样切片，但本例 Provider 的验证仍用完整四行，不能拿 Loader 的存在推断验证会分批。

```python
# cases/linear_point/problem/__init__.py
from mlblack.problems import TabularNeuralRegressionProblem

def build_problem(data):
    return TabularNeuralRegressionProblem(data, use_valid_objective=True)
```

```python
# cases/linear_point/build_solver.py
from mlblack.integrations.nsgablack_gradient import build_gradient_trainer
from mlblack.pipeline import NumericBatchSchedule
from mlblack.representations import NeuralGraphRepresentation
from nsgablack.project import apply_solver_component_overrides
from .config import BATCH_SIZE
from .pipeline.main import build_pipeline
from .problem import build_problem

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("this recipe uses its declared data and budget")
    data, schedule_config = build_pipeline(BATCH_SIZE)
    schedule = NumericBatchSchedule(data, schedule_config)
    representation = NeuralGraphRepresentation.mlp(input_dim=1, hidden_layers=(2,),
        output_dim=1, activation="tanh", random_seed=17, representation_name="batch_mlp")
    solver = build_gradient_trainer(problem=build_problem(data), representation=representation,
        method="gradient.adamw", compute_backend="torch", learning_rate=.01,
        data_schedule=schedule, resource_context=resource_context, run_name="batch_regression")
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(4)
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

正规工厂创建 TorchEvaluationProvider 并把 schedule 传入。Provider 在求值时调用 next_train，把 batch 注入局部 ML context；TabularNeuralRegressionProblem 用它求训练损失和梯度。验证仍用完整验证集，原始目标是 valid.mse，避免把不同小批训练误差直接当统一 incumbent 比较口径。默认 Provider 使用 StateRef/COW 状态转移和原优化控制面；Case 不手写 epoch/optimizer 循环，也不申请 GPU。

```python
# run_batch_and_report.py
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
    if value.best_feedback is None:
        raise ValueError("no evaluated batch-model feedback")
    payload = {"run_id": run.run_id, "objectives": value.best_objectives.tolist(),
        "metrics": dict(value.best_feedback.metrics), "signals": dict(value.best_feedback.signals),
        "model_ref": None if value.best_model_ref is None else value.best_model_ref.as_dict()}
    path = root / "results" / "batch.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

**怎样判断接对：** 新 batch.json 应有 valid.mse、train.mse、provider.batch_size 和 signals.batch_indices/batch；目标是一项 valid MSE，train.mse 属于该次小批，不是全部八行训练 MSE。这里读取的是最佳已评估模型的那次 batch 证据，不保证是最后 batch。正式模型 Artifact 沿 TabularNeuralRegressionProblem 的 NeuralGraphArtifact 路径发布，Torch 状态走正式 NPZ 序列化和 model_ref；没有 unsafe pickle，也不以未评估后继作为结果。

**运行入口：** 在副本根先执行 `python run_project.py --check --build-check`，再执行 `python run_batch_and_report.py`。前者也会构造实际组件，后者会真实训练；本轮两条都未执行。四个逻辑提交不是四个 epoch，也不保证等于恰好四次数据求值。必须结合真实 provider batch 证据，而不是预算参数猜测消费次数。

### 变体一：完整训练集作为一个 batch

**目的：** 去掉小批差异，仍复用同一 Provider/训练装配与正式结果路径。

**改在哪里：** 完整替换同一 config.py，其他工厂都消费此值。

```python
# cases/linear_point/config.py
BATCH_SIZE = 8
```

**行为变化：** Loader 每轮一批覆盖0…7；Schedule 每次 next_train 交付完整八行并推进 epoch。valid.mse 仍用全部四行，训练指标现在对应完整训练集。

**限制：** NumericBatchSchedule 是按需持续跨 epoch，**不消费 DatasetStreamConfig.repeat 作为停止条件**；停止仍由 Solver 预算负责。Schedule 的 get_state/set_state 校验行数、batch_size/shuffle/drop_last/seed，不验证整份数据内容指纹；恢复必须由应用保证数据与顺序相同。正式 checkpoint 中 Schedule 随 Evaluation Provider 保存；本例未额外装检查点插件、未执行恢复试验，不能将这份接线写成恢复已验收。该工厂目前只允许 Torch 路由接 data_schedule，不能把 compute_backend 改成 NumPy 就假定同样支持。

源码：`mlblack/pipeline/datasets.py::NumericBatchLoader/NumericBatchSchedule`、`integrations/nsgablack_gradient.py`、`backends/torch_neural/evaluation_provider.py`、`problems/neural.py::TabularNeuralRegressionProblem`、`core/provider_problem.py`、`core/artifact_provider.py`。
