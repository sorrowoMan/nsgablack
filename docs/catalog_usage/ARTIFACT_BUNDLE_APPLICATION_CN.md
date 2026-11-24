# 从正式 ML Case 的已提交结果整理 ArtifactBundle

## mlblack.core.artifact_bundle · 把模型描述与运行报告收拢成可查看的交付摘要

**什么时候用：** 已经通过正式 Case 完成一次训练，希望把模型说明、运行指标和相关元数据整理成同一个对象，并生成本地 JSON/HTML 供查看。ArtifactBundle 是边界值，不负责训练或决定哪个模型最好；已有 Case 的权威 Artifact 引用仍由原发布事务管理。

**先准备什么：** 使用 mlblack 仓库现有 Project `examples/cases/catalog_codec_demo/` 的 `cases/linear_point/`。保留其数据、LinearPointRepresentation、回归 Problem、梯度 Adapter、DEFAULTS、运行入口与 Project L0。这个 CPU 小例子使用 24 条两特征合成数据，LearningSolver 的 incumbent 决定 best_model/best_feedback。以下路径相对该 Project，不要另建一个独立训练循环。本章代码已按源码核对，没有运行这份新增观察器的 Project。

**放在哪：** 新建 `cases/linear_point/plugins/bundle.py`，再按下方完整 builder 接上。代码在 `on_solver_finalized` 才读取结果；不在 teardown 前的 on_solver_finish 把“正在收尾”当成成功发布。

**接入步骤：** 先写观察器及其值构造函数。参数 result 是该 Solver 的正式 TrainerResult 投影，不是另造一个带假字段的模型对象。模型与反馈都取自同一个 result。

```python
# cases/linear_point/plugins/bundle.py
import json
from pathlib import Path
from mlblack.core.artifacts import ArtifactBundle, ModelArtifact, RunReport
from mlblack.core.artifact_viewer import save_artifact_html
from nsgablack.plugins.base import Plugin


def build_bundle(control, result):
    model_artifact = None
    if result.best_model is not None:
        model_artifact = ModelArtifact(
            name=control.run_name, model=result.best_model,
            family="linear_point", head="point",
            metadata={"source": "finalized_solver_incumbent"})
    feedback = result.best_feedback
    report = RunReport(
        run_name=control.run_name,
        status=str(result.report.get("status", "unknown")),
        metrics={} if feedback is None else dict(feedback.metrics),
        components={"representation": "linear_point"},
        metadata={"artifact_names": sorted(result.artifact_refs)})
    return ArtifactBundle(model_artifact=model_artifact, run_report=report,
        metadata={"run_id": control.run_session.run_id,
                  "purpose": "local_view_of_finalized_result"})


class BundleObserver(Plugin):
    def __init__(self, output):
        super().__init__(name="bundle_observer")
        self.output = Path(output)

    def on_solver_finalized(self, raw_result):
        result = self.solver.export_case_result(raw_result)
        bundle = build_bundle(self.solver, result)
        self.output.mkdir(parents=True, exist_ok=True)
        (self.output / "summary.json").write_text(
            json.dumps(bundle.describe(), ensure_ascii=False, indent=2, allow_nan=False),
            encoding="utf-8")
        save_artifact_html(bundle, self.output / "bundle.html", title="线性回归运行摘要")
```

接着完整替换这个 Case 的规范 builder。原 `plugins/__init__.py` 不必额外导出观察器，因为这里直接从子模块导入。

```python
# cases/linear_point/build_solver.py
from pathlib import Path
from mlblack.integrations.nsgablack_control import build_learning_solver
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from nsgablack.project import apply_solver_component_overrides
from .adapter import build_adapter
from .config import DEFAULTS
from .pipeline import build_pipeline
from .problem import build_problem
from .plugins.bundle import BundleObserver


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {**DEFAULTS, **dict(config or {})}
    data = build_pipeline(seed=settings["seed"], n_samples=settings["n_samples"])
    representation = LinearPointRepresentation(LinearPointConfig(
        n_features=data.n_features, feature_names=data.effective_feature_names,
        random_seed=int(settings["seed"])))
    solver = build_learning_solver(problem=build_problem(data), representation=representation,
        adapter=build_adapter(learning_rate=settings["learning_rate"]),
        resource_context=resource_context, run_name="catalog_linear_point")
    solver.set_random_seed(int(settings["seed"]))
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    solver.add_plugin(BundleObserver(Path(__file__).resolve().parent / "results" / "bundle"))
    return solver
```

数据进入表示与 Problem，Adapter 提出参数候选，Solver 维护原始反馈、incumbent 和正式发布；观察器在完成通知中把该结果整理成 Bundle。`export_case_result` 在这里是读取/投影接口，不再次 fit。观察器不重新挑模型，也不把 JSON 路径登记成权威 Artifact。

**怎样判断接对：** 查看 `cases/linear_point/results/bundle/summary.json` 与 `bundle.html`。JSON 有 model_artifact、trainer_state、run_report、snapshot_refs、metadata 五个顶层键；metadata.run_id 应是本轮运行。成功取得模型时，model_artifact 描述包含 name/family/head/model_type；run_report.metrics 来自 best_feedback.metrics，artifact_names 来自正式结果的已有引用。没有模型时 model_artifact 可以为 None，不能凭文件存在断言有最佳模型。trainer_state 在本例为 None，snapshot_refs 默认空；这份本地摘要不宣称能够恢复训练。

字段边界必须准确：`TrainerStateArtifact` 接受 payload、signature、version、metadata，不接受 name 或 model。`ArtifactBundle.describe()` 不接受 include_model；要明确查看模型载荷，应对已有非空 `bundle.model_artifact` 调用 `describe(include_model=True)`，本例 JSON/HTML 刻意使用默认描述，避免把模型活对象当成 JSON。`bundle.save(path)` 是本地 Bundle 保存方法，也不能代替 Case 发布事务或权威收据。

**运行入口：** 在 mlblack 仓库根先执行 `python examples/cases/catalog_codec_demo/run_project.py --check --build-check`，再执行 `python examples/cases/catalog_codec_demo/run_project.py`。这个 Project 的默认组明确只运行 linear_point。应同时核对本轮正式 Project 结果和本地摘要；旧 JSON 或已有 HTML 不算新运行收据。读取最终值不会为了展示而创建新的 Adapter Unit。

### 变体一：只保留运行报告，不保留模型载荷

若只想整理监控/审计信息，完整替换 `plugins/bundle.py` 的 build_bundle；观察器、builder 和运行入口保持不变。这个选择减少 Bundle 持有的对象，并不删除 Solver 已发布的正式模型。

```python
def build_bundle(control, result):
    feedback = result.best_feedback
    report = RunReport(
        run_name=control.run_name,
        status=str(result.report.get("status", "unknown")),
        metrics={} if feedback is None else dict(feedback.metrics),
        components={"representation": "linear_point"},
        metadata={"artifact_names": sorted(result.artifact_refs)})
    return ArtifactBundle(run_report=report,
        metadata={"run_id": control.run_session.run_id, "purpose": "report_only"})
```

输出 model_artifact/trainer_state 均为 None，run_report 仍来自同一次正式结果。这个 Bundle 可以描述运行，却不能单独用于模型推理或恢复。需要训练状态时，应消费正式检查点捕获点交付的可传输 payload，不能在结束通知中随意重新复制活状态，更不能把 TrainerStateArtifact 当作 ModelArtifact 来填字段。
