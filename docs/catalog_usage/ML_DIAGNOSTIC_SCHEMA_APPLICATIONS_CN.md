# 诊断与装配配置：不需要训练时也使用正式 Case

本书没有执行诊断、训练或Project。它给出完整文件和实际消费者，不把一个配置对象称为已经装配的算法。每个主例使用独立的完整 `mlblack/examples/cases/catalog_codec_demo/` 副本，保留默认linear组、linear_point Case包、L0和规范别名。

## mlblack.core.diagnostic · 一次诊断怎样接到正式运行

**什么时候用：** 已有一段数据诊断函数，希望使用统一的Case资源、求值、结果、错误与发布生命周期，不写自己的Trainer.run。本例计算固定16条观测的均值和方差，不进行候选搜索或模型拟合。

**先准备什么：** 当前三仓和NumPy。候选只是触发诊断的语义哨兵，不是16条数据；数据由pipeline返回并由runner闭包持有。DiagnosticProblem会将Mapping结果转为Feedback，仅保留紧凑标量metrics。

**放在哪：** 替换Case的pipeline/main.py、problem/__init__.py、build_solver.py。Project根保存下文run_diagnostic_and_report.py。原Codec/Adapter工厂不再被这个builder调用，不能同时又装配一个梯度循环。

**接入步骤：** 完整文件如下。

```python
# cases/linear_point/pipeline/main.py
import numpy as np

def build_pipeline():
    return np.arange(16, dtype=float)
```

```python
# cases/linear_point/problem/__init__.py
import numpy as np

def diagnostic_runner(values):
    data = np.asarray(values, dtype=float).copy()
    if data.ndim != 1 or not len(data) or not np.isfinite(data).all():
        raise ValueError("a finite observed sequence is required")
    def run(context):
        return {"objective": float(np.var(data)), "status": "ok",
                "metrics": {"count": len(data), "mean": float(np.mean(data)),
                            "preview": data[:3].tolist()}}
    return run
```

```python
# cases/linear_point/build_solver.py
from mlblack.core.diagnostic import DiagnosticProblem, DiagnosticRepresentation
from mlblack.integrations import build_diagnostic_solver
from .pipeline.main import build_pipeline
from .problem import diagnostic_runner

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this recipe has explicit diagnostic inputs")
    solver = build_diagnostic_solver(diagnostic_runner(build_pipeline()),
        name="observed_sequence_diagnostic", resource_context=resource_context)
    if not isinstance(solver.semantic_problem, DiagnosticProblem):
        raise TypeError("expected the canonical diagnostic Problem")
    if not isinstance(solver.model_representation, DiagnosticRepresentation):
        raise TypeError("expected the semantic placeholder representation")
    solver.set_random_seed(17)
    solver.set_bias_module(None, enable=False)
    return solver
```

工厂真正构造DiagnosticProblem+DiagnosticRepresentation+FixedCandidateAdapter，并登记一代预算控制；资源传入正式learning solver，不另建私有执行器。Representation.init的UnknownState含一个零和诊断metadata，decode返回None。Problem忽略模型候选，调用runner一次，返回单目标Feedback；因此此默认路线没有模型可发布，best_model_ref应为空。不要给不存在的模型Artifact编一个成功路径。

Project根完整结果入口：

```python
import json
from pathlib import Path
from blackbase.types import TrainerResult
from mlblack.project.project_runner import execute_project

def main():
    root = Path(__file__).resolve().parent
    run = execute_project(root)
    case = next(x for x in run.case_results if x.request.case_name == "linear_point")
    case.raise_for_failure()
    value = TrainerResult.from_dict(case.output)
    if value.best_feedback is None:
        raise RuntimeError("diagnostic feedback missing")
    payload = dict(run_id=run.run_id, objectives=value.best_objectives.tolist(),
        metrics=dict(value.best_feedback.metrics),
        model_ref=None if value.best_model_ref is None else value.best_model_ref.as_dict())
    target = root/"results"/"diagnostic.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False,
                                 indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

**怎样判断接对：** diagnostic.json来自本次run_id；原始目标为21.25，count16、mean7.5、model_ref为空。preview数组不会进入紧凑metrics，这不是数据丢失bug；大结果应另走正式Artifact或保存在Problem实例供适当观察，不塞共享context。诊断status=ok只说明runner正常返回，不证明任何统计假设成立。

**运行入口：** 副本根先`python run_project.py --check --build-check`，再`python run_diagnostic_and_report.py`。后者执行一次正式Project并取其结果；不要先run_project再为了读结果又执行一遍。

### 变体：直接返回正式Feedback

**目的：** 显式控制loss、metrics和约束字段，避免依赖Mapping默认objective=0。**改在哪里：** problem/__init__.py中保留data校验，将run函数完整替换为：

```python
def run(context):
    from blackbase.types import Feedback
    return Feedback(objectives=np.array([float(np.var(data))]),
        constraints=np.zeros(0), metrics={"count": len(data), "mean": float(np.mean(data))},
        loss=float(np.var(data)))
```

**行为变化：** Feedback直接透传，不再经过紧凑Mapping投影。**限制：** 仍须让metrics可传输、控制大小；不允许把方差分数当模型权重或优化后的预测器。

## mlblack.schema.scaffold_config · 配置必须交给真实装配消费者

**什么时候用：** 希望把数据schema和单个内层Trainer装配选择保存成JSON，由Case实际读取；不是把流程编排重新塞进ScaffoldConfig。跨Case执行仍属于Project。

**先准备什么：** 另一份完整Project副本；按ML_CLASSICAL_DATA_ASSEMBLY_APPLICATIONS_CN.md的classical.assembly.trainer保留完整两特征NumericDataView pipeline和run_classical_and_report.py。此例仍为原始线性回归数据，不新增隐藏数据源。

**放在哪：** Case根保存scaffold_config.json；替换build_solver.py。schema对原始列名描述，既不自动读取CSV，也不自动构造训练/验证切分。

**接入步骤：** JSON完整内容：

```json
{
  "name": "catalog_schema_linear",
  "version": "0.1",
  "schema": {"features": ["a", "b"], "targets": ["target"], "strict": true},
  "inner_training": {
    "trainer": {"preset": "linear_point", "run_name": "schema_linear",
      "params": {"learning_rate": 0.03, "l2": 0.0, "complexity_weight": 0.0,
                 "max_components": 3, "energy_threshold": 0.999}}
  },
  "metadata": {"purpose": "explicit_schema_and_single_trainer"}
}
```

build_solver.py完整内容：

```python
from pathlib import Path
from blackbase.resources import coerce_resource_context
from mlblack.assembly import ScaffoldConfig, TrainerAssemblySpec, build_trainer, load_scaffold_config
from .pipeline.main import build_pipeline

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("edit the source-owned scaffold_config.json explicitly")
    scaffold = load_scaffold_config(Path(__file__).with_name("scaffold_config.json"))
    if not isinstance(scaffold, ScaffoldConfig):
        raise TypeError("expected parsed scaffold configuration")
    data = build_pipeline()
    schema = scaffold.schema_spec()
    if tuple(data.feature_names) != schema.feature_keys:
        raise ValueError("pipeline output columns do not match declared raw schema")
    trainer_payload = dict(scaffold.inner_training["trainer"])
    trainer_payload["resource_context"] = ({} if resource_context is None
        else coerce_resource_context(resource_context).as_dict())
    solver = build_trainer(TrainerAssemblySpec.from_value(trainer_payload), data)
    solver.set_random_seed(17)
    solver.set_max_steps(6)
    solver.set_bias_module(None, enable=False)
    return solver
```

这段代码实际消费ScaffoldConfig、列schema、inner_training.trainer以及Project grant。没有把整个JSON直接展开给Trainer，metadata/version也不暗中改变算法。当前build_trainer的linear_point别名走正交线性preset，其实际模型和Artifact与classical.assembly.trainer一致；不是裸候选Codec的另一个同名入口。

**怎样判断接对：** 构造检查显示实际Trainer/Adapter；本次classical.json有评估反馈与模型引用。将schema中的a改成不存在的列，应在数据契约检查处失败，不能静默错位。ScaffoldConfig.from_value拒绝旧flow字段；反序列化成功本身不证明inner_training里所有preset参数都受支持。

**运行入口：** 副本根`python run_project.py --check --build-check`，再`python run_classical_and_report.py`。没有为了读配置另外fit一个模型。

### 变体：减小学习率

**目的：** 保持数据schema与Case不变，只改一个明确训练参数。**改在哪里：** JSON的learning_rate从0.03改为0.01，其余原样。

```python
# 维护脚本中等价的显式改法；只处理已加载配置，不写运行中的solver。
def with_smaller_step(scaffold):
    import json
    payload = json.loads(json.dumps(scaffold.as_dict()))
    payload["inner_training"]["trainer"]["params"]["learning_rate"] = .01
    return ScaffoldConfig.from_value(payload)
```

**行为变化：** 六次更新步长减小，模型维度与列顺序不变。**限制：** as_dict中的inner_training是浅层拷贝，所以这里先独立复制JSON值；这不是允许复制Provider/锁等任意活对象图。

源码核对：mlblack/core/diagnostic.py、integrations/nsgablack_diagnostic.py、assembly/schema/spec.py、assembly/schema/parser.py、assembly/builders.py。
