# 神经时序：七种路由、概率目标与滚动起点

本页只核对当前源码与静态片段，未运行模型、训练、下载或网络调用。结构 Spec 是模型描述，不是求解算法；preset 把它交给 Representation/Codec、Problem、Provider 和共享优化控制面。

## neural.temporal · 同一窗口数据，显式选择七种真实预设

**什么时候用：** 想在固定一步预测任务上更换 LSTM、TCN、Transformer、N-BEATS、DeepAR、PatchTST 或 TFT 路由，并明确哪里变成概率预测。

**先准备什么：** 当前三仓、NumPy、CPU PyTorch；DeepAR 指标还使用 SciPy。复制整个 `mlblack/examples/cases/temporal_neural_compare`，保留 Project L0/Case结构。只改 `cases/temporal_lstm` 作这本书的宿主；名字不决定实际模型。下方单Case组避免默认组自动运行全部七个 Case。数据为16训练/4验证窗口，每窗4个已观测值、下一值为标签。

**放在哪：** 完整替换宿主的 config.py、pipeline/main.py、build_solver.py；新建 solver/temporal.py。原 Problem/Adapter 工厂不由新 builder 调用，实际组件由 preset 建立。再保存末节 Project组与薄报告入口。

**接入步骤：** 先固定连续窗口数据，再由 MODE 选择实际预设及其对应损失，最后通过正式 Project 运行并读取发布结果。

```python
# cases/temporal_lstm/config.py
MODE = "lstm"
```

```python
# cases/temporal_lstm/pipeline/main.py
from mlblack.pipeline.synthetic_temporal import build_sine_forecast_data_view

def build_pipeline(*, config=None, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this recipe uses a frozen synthetic window definition")
    return build_sine_forecast_data_view(n_train=16, n_valid=4, sequence_length=4,
        noise_std=.03, frequency=.2, random_seed=17)

def run_pipeline_slot(*args, **kwargs):
    return build_pipeline(**kwargs)
```

这个公开数据工厂从一条连续序列先生成20个相邻窗口再按时间切分：X是二维 `(n,4)`，按由旧到新排列，后端按 sequence_length=4/input_dim=1 解释。较晚验证窗口能使用较早验证期已经观测到的真实值，是一步滚动设定；不等于从一个截点递推四步，不能把验证标签用于输入当时尚未知的位置。

```python
# cases/temporal_lstm/solver/temporal.py
from mlblack.presets import (build_temporal_lstm_forecast_trainer,
    build_temporal_tcn_forecast_trainer, build_temporal_transformer_forecast_trainer,
    build_temporal_nbeats_forecast_trainer, build_temporal_deepar_forecast_trainer,
    build_temporal_patchtst_forecast_trainer, build_temporal_tft_forecast_trainer)

def build_temporal(data, mode, grant):
    common = dict(input_dim=1, sequence_length=4, output_dim=1, compute_backend="torch",
        optimizer="adamw", learning_rate=.01, random_seed=17,
        resource_context=grant, run_name="temporal_"+mode)
    if mode == "lstm":
        return build_temporal_lstm_forecast_trainer(data, hidden_dim=4,
            num_layers=1, dropout=0., bidirectional=False, **common)
    if mode == "tcn":
        return build_temporal_tcn_forecast_trainer(data, channels=(4,), kernel_size=2,
            dilation_base=2, dropout=0., **common)
    if mode == "transformer":
        return build_temporal_transformer_forecast_trainer(data, hidden_dim=4,
            num_layers=1, num_heads=1, ffn_expansion_ratio=2., dropout=0., **common)
    if mode == "nbeats":
        return build_temporal_nbeats_forecast_trainer(data, hidden_dim=4, theta_dim=2,
            num_stacks=1, num_blocks=1, share_weights=False, dropout=0., **common)
    if mode == "deepar":
        return build_temporal_deepar_forecast_trainer(data, hidden_dim=4,
            num_layers=1, alpha=.1, dropout=0., **common)
    if mode == "patchtst":
        return build_temporal_patchtst_forecast_trainer(data, patch_len=2, stride=2,
            hidden_dim=4, num_layers=1, num_heads=1, ffn_dim=8, dropout=0., **common)
    if mode == "tft":
        return build_temporal_tft_forecast_trainer(data, hidden_dim=4,
            num_layers=1, num_heads=1, dropout=0., **common)
    raise ValueError("unknown temporal route")
```

每个工厂实际调用同名 NeuralGraphSpec.temporal_*，声明相应块、输入形状和 Head，再交 NeuralGraphRepresentation/Codec 做后端 lowering。这里的 Spec 目录键不是七个额外 Adapter，也不提前创建算法 Unit。PatchTST 的 patch_len/stride 针对4步历史，Transformer/TFT 的 hidden_dim 能被 num_heads 整除；不要把所有路由强塞同一参数字典。框架实现采用这些模型族的结构思想，不因此保证复现外部项目的所有细节。

```python
# cases/temporal_lstm/build_solver.py
from nsgablack.project import apply_solver_component_overrides
from .config import MODE
from .pipeline.main import build_pipeline
from .solver.temporal import build_temporal

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("edit explicit temporal config")
    solver = build_temporal(build_pipeline(), MODE, resource_context)
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(2)
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

LSTM/TCN/Transformer/N-BEATS/PatchTST/TFT 配 TemporalNeuralForecastingProblem，输出 forecast，默认单目标 valid.mse，训练梯度仍用训练 MSE。对应 Problem 发布 NeuralGraphArtifact：模型参数NPZ、图/布局元数据与正式 best_model_ref。

DeepAR 配 **TemporalNeuralProbabilisticForecastingProblem** 和 deepar Head，输出 mu/log_sigma，经 Gaussian NLL；alpha=.1 控制指标区间名义覆盖，不是训练步长。默认目标 valid.nll，反馈 loss 在该实现仍是训练NLL，不能把它们写成同一个数。其当前 Problem 没有专用 build_model_artifact，正式 Provider 仍可将 Torch Module 按原模型序列化路径保存NPZ，但不会自动补出点预测 Problem 那份完整专用 NeuralGraphArtifact 描述；结构配置须随工程保存。

**怎样判断接对：** 新结果JSON的单目标对应实际模式：点预测valid.mse，概率模式valid.nll；原始目标不因模型名字改变成模型预测值。点预测train/valid有mse/rmse/mae，DeepAR有效验证集有nll/crps/picp/rmse/mae，微分路径不保证返回所有train概率诊断。picp不是校准保证；两步不代表两epoch或可靠模型比较。读取已评估incumbent对应反馈/模型引用，不拿后继参数当输出。

**运行入口：** 用末节catalog_one组执行一次；不运行旧default组来补报告。语法与装配说明没有提供七次运行证据，不能据此判断哪一种模型更好。

### 变体一：换成有限感受野的 TCN

**目的：** 以卷积路由替换递归单元。**改在哪里：** 完整替换配置。

```python
MODE = "tcn"
```

**行为变化：** 实际消费 channels/kernel_size/dilation_base，仍是点预测任务。**限制：** 不声称当前短历史已覆盖真实长期周期。

### 变体二：明确 Transformer 的头维约束

**目的：** 使用注意力路由。**改在哪里：** 完整替换配置。

```python
MODE = "transformer"
```

**行为变化：** 使用4维/1头/1层编码与forecast Head。**限制：** 不加载预训练语言模型，不等于HF SFT。

### 变体三：改为残差堆叠 N-BEATS

**目的：** 使用明确的一栈一块结构。**改在哪里：** 完整替换配置。

```python
MODE = "nbeats"
```

**行为变化：** theta_dim=2、num_stacks/num_blocks被实际工厂消费。**限制：** 不是模型训练循环层数，不能与Solver步数混用。

### 变体四：概率预测同时改变 Head 与 Problem

**目的：** 学习Gaussian尺度。**改在哪里：** 完整替换配置。

```python
MODE = "deepar"
```

**行为变化：** 自动配套概率Problem/NLL及mu/log_sigma输出。**限制：** 不只是把点模型多加一个Bias，也不保证Gaussian假设成立。

### 变体五：用两个长度二的历史补丁

**目的：** 使用PatchTST route。**改在哪里：** 完整替换配置。

```python
MODE = "patchtst"
```

**行为变化：** patch_len=2/stride=2对4步历史产生明确补丁。**限制：** 历史长度/patch布局改变须匹配新模型状态。

### 变体六：TFT 路由

**目的：** 使用当前实现的门控/注意力结构。**改在哪里：** 完整替换配置。

```python
MODE = "tft"
```

**行为变化：** TFT Spec由该预设实际构造，仍使用forecast Problem。**限制：** 本例只有单变量已观测历史，不冒称已支持任何业务静态/已知未来协变量设定。

## neural.temporal.run · 单 Case 分组与正式结果读取

在原 Project `project_config.py` 最后追加以下内容，保留L0及其它分组：

```python
STAGES.append(dict(name="catalog_one", cases=["temporal_lstm"], policy="serial",
    resource_requests={"temporal_lstm": dict(threads=1, device="cpu", backend="local")}))
GROUPS["catalog_one"] = dict(stages=["catalog_one"])
```

Project根新增 `run_temporal_and_report.py`：

```python
import json
from pathlib import Path
from blackbase.types import TrainerResult
from mlblack.project.project_runner import execute_project

def main():
    root = Path(__file__).resolve().parent
    run = execute_project(root, group="catalog_one")
    case = next(c for c in run.case_results if c.request.case_name == "temporal_lstm")
    case.raise_for_failure()
    value = TrainerResult.from_dict(case.output)
    if value.best_feedback is None or value.best_model_ref is None:
        raise ValueError("evaluated feedback and model reference required")
    payload = {"run_id": run.run_id, "objectives": value.best_objectives.tolist(),
        "loss": value.best_feedback.loss, "metrics": dict(value.best_feedback.metrics),
        "signals": dict(value.best_feedback.signals), "model_ref": value.best_model_ref.as_dict()}
    path = root / "results" / "temporal.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

副本根先执行 `python run_project.py --group catalog_one --check --build-check`，再执行 `python run_temporal_and_report.py`。后一条会真实训练，只运行一个宿主Case。核对正式Case状态/新run_id，JSON为观察副本，不是额外发布权威；本轮没有运行。

## neural.temporal.rolling · 只评估同一参数模型，不在每个起点重新训练

**什么时候用：** 希望每个候选是同一组神经参数，在多个历史起点评估误差；当前 TemporalNeuralRollingOriginProblem 没有梯度，不应直接装Adam当它可微。

**先准备什么：** 上面完整Project的另一份副本，同样保留单Case组/报告入口。三仓、NumPy、CPU Torch。20个有序观测、4步历史、horizon=1；搜索参数模型，不在各origin调用fit。

**放在哪：** 本变体完整替换宿主pipeline/main.py、problem/__init__.py、build_solver.py；无需上节MODE/solver.temporal工厂。运行组仍只调用temporal_lstm Case。

**接入步骤：** 先建立有序原始序列，交给只读滚动评估 Problem；再用 LSTM Spec 表示参数，最后装配不依赖梯度的搜索与正式结果发布。

```python
# cases/temporal_lstm/pipeline/main.py
import numpy as np
from mlblack.pipeline import TimeSeriesDataView

def build_pipeline(*, config=None, resource_context=None, component_overrides=None):
    t = np.arange(20, dtype=float)
    return TimeSeriesDataView(y=np.sin(.2*t), time_index=tuple(range(20)))

def run_pipeline_slot(*args, **kwargs):
    return build_pipeline(**kwargs)
```

```python
# cases/temporal_lstm/problem/__init__.py
from mlblack.problems import TemporalNeuralRollingOriginProblem
from mlblack.core.artifacts import TorchModelArtifact

class RollingProblem(TemporalNeuralRollingOriginProblem):
    def build_model_artifact(self, model, context=None):
        return TorchModelArtifact(name="rolling_lstm", model=model, family="temporal",
            head="forecast", representation={"sequence_length": 4, "input_dim": 1,
                "hidden_dim": 2, "num_layers": 1, "output_dim": 1})

def build_problem(data):
    return RollingProblem(data, sequence_length=4, min_train_size=8, horizon=1,
        max_origins=4, objective_metrics=("rolling.rmse",), seasonal_period=1)
```

```python
# cases/temporal_lstm/build_solver.py
from mlblack.representations import NeuralGraphSpec, NeuralGraphRepresentation
from mlblack.integrations.nsgablack_control import build_learning_solver
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter
from nsgablack.project import apply_solver_component_overrides
from .pipeline.main import build_pipeline
from .problem import build_problem

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("this recipe fixes its rolling task")
    spec = NeuralGraphSpec.temporal_lstm(input_dim=1, sequence_length=4,
        hidden_dim=2, num_layers=1, output_dim=1)
    solver = build_learning_solver(problem=build_problem(build_pipeline()),
        representation=NeuralGraphRepresentation(spec),
        adapter=build_optimization_adapter("search.random_gaussian", population_size=2,
            mutation_scale=.02, random_seed=17, objective_aggregation="first"),
        compute_backend="torch", resource_context=resource_context, run_name="rolling_lstm")
    solver.set_bias_module(None, enable=False)
    solver.set_max_steps(2)
    solver.set_random_seed(17)
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

**怎样判断接对：** 共用temporal.json的单目标是rolling.rmse，指标有rolling.origins/horizon/min_train_size及误差；这例max_origins=4从有效起点范围等距抽取四个，不是只取末四个。每个origin都只用到该时刻已观测的4步，参数不随origin更新。Artifact发布匹配的Torch参数/结构描述，不重新fit恢复已评估模型。预算非常小，不代表神经参数搜索有效。

**运行入口：** 使用同一catalog_one组和run_temporal_and_report.py；主例来源与本节文件不能混用，执行会求值模型但不会在每个origin训练。仍由Project授权，报告不是运行收据。

### 变体一：统计全部合法起点

**目的：** 不抽样origin。**改在哪里：** problem/__init__.py保留上面类，完整替换工厂：

```python
def build_problem(data):
    return RollingProblem(data, sequence_length=4, min_train_size=8, horizon=1,
        max_origins=None, objective_metrics=("rolling.rmse",), seasonal_period=1)
```

**行为变化：** 每个候选调用更多前向，反馈仍同一RMSE口径。**限制：** 不因此拥有样本外训练评测拆分；这是当前这条序列上的模型选择目标，独立最终测试仍需另留时间段。只给一个forecast标量时，本例固定horizon1，不从多输出最后一项猜任意预测任务。

源码：`mlblack/presets/neural.py`、`pipeline/synthetic_temporal.py`、`representations/codecs/neural/specs.py`、`backends/torch_neural/temporal.py`、`problems/neural.py`、`core/artifact_provider.py`。
