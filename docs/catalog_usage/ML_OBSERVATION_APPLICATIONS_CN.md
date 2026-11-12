# 实验观察：记录、授权审计、查询与HTML各自是什么

本书没有执行训练、算法、SQLite、网络或服务。所有代码均为当前源码静态核对的使用说明。主例默认内存记录；SQLite只是明确选择的变体，不会因打开Catalog而自动创建数据库。

## observation.case

**什么时候用：** 希望在完整ML Case中观察训练/送评/提交步骤，知道最终使用什么L0资源，并在正式结果发布后导出可读页面。ExperimentTrackerCapability/ResourceAuditCapability共享Plugin生命周期；Capability是扩展基类，不是第二套Trainer控制器。

**先准备什么：** 完整复制 `mlblack/examples/cases/catalog_codec_demo/`，保留原Project/default/linear_point、原pipeline/main.py与规范入口、1CPU线程L0。原管线生成24行两特征线性数据；依赖三仓和NumPy。默认只使用InMemoryExperimentStore，不连接任何服务。

**放在哪：** 新建 Case config.py、plugins/observations.py，替换build_solver.py。原数据管线保留。再保存下一节的正式Project结果入口；它只运行一次，不先fit再补跑报告。

**接入步骤：** 完整文件如下。Tracker只记录观察事件，模型由原线性Problem和同一优化控制面产生。资源审计读取已有grant，不分配线程。

```python
# cases/linear_point/config.py
STORE_KIND = "memory"  # memory / sqlite
RECORD_EVALUATIONS = False
```

```python
# cases/linear_point/plugins/observations.py
import json
from pathlib import Path
from mlblack.core.capability import Capability
from mlblack.catalog.experiment.dashboard import export_experiment_html

class ObservationExport(Capability):
    name = "case_observation_export"
    def __init__(self, store, output_dir):
        super().__init__(name=self.name)
        self.store, self.output_dir = store, Path(output_dir)

    def on_solver_finalized(self, result):
        control = self.solver
        rows = self.store.list(run_name=control.run_name)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        export_experiment_html(self.output_dir/"events.html", rows)
        audit = {name: control.context_store.get(name) for name in (
            "resource.audit.fit_start", "resource.audit.last_step", "resource.audit.fit_end")}
        payload = {"run_id": control.run_session.run_id, "run_name": control.run_name,
            "record_count": len(rows), "events": [x.as_dict() for x in rows],
            "resource_audit": audit}
        (self.output_dir/"events.json").write_text(json.dumps(payload,
            ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
```

```python
# cases/linear_point/build_solver.py
from pathlib import Path
from uuid import uuid4
from mlblack.capabilities.tracking import (ExperimentTrackerCapability,
    ExperimentTrackerConfig, InMemoryExperimentStore, SQLiteExperimentStore)
from mlblack.capabilities.resource_audit import ResourceAuditCapability
from mlblack.presets import build_linear_point_trainer
from .pipeline import build_pipeline
from .plugins.observations import ObservationExport
from .config import STORE_KIND, RECORD_EVALUATIONS

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this recipe uses explicit component settings")
    output = Path(__file__).resolve().parents[2]/"results"/"observations"
    if STORE_KIND == "memory":
        store = InMemoryExperimentStore()
    elif STORE_KIND == "sqlite":
        output.mkdir(parents=True, exist_ok=True)
        store = SQLiteExperimentStore(output/"experiments.sqlite3")
    else:
        raise ValueError("unknown observation store")
    solver = build_linear_point_trainer(build_pipeline(seed=17, n_samples=24),
        method="gradient.sgd", learning_rate=.03, l2=0., use_valid_objective=False,
        random_seed=17, run_name="catalog_observation_"+uuid4().hex[:10])
    if resource_context is not None:
        solver.set_resource_context(resource_context)
    solver.set_bias_module(None, enable=False)
    solver.set_max_steps(3)
    solver.add_plugin(ExperimentTrackerCapability(store=store,
        config=ExperimentTrackerConfig(record_steps=True,
                                      record_evaluations=RECORD_EVALUATIONS)))
    solver.add_plugin(ResourceAuditCapability())
    solver.add_plugin(ObservationExport(store, output))
    return solver
```

Case的context_keys.json合并以下声明（已有声明保留）：

```json
["experiment.record_count", "resource.audit.fit_start", "resource.audit.last_step", "resource.audit.fit_end"]
```

Tracker的fit_start对应on_solver_init，step_end对应**已提交逻辑代**的on_generation_end；并非每次失败物理尝试。fit_end映射到on_solver_finish，发生在teardown/正式finalization之前，所以它不是“模型已经发布成功”的收据。ObservationExport在finalized后读本次已有记录并写文件，不再evaluate；失败运行可能没有这份导出，但Tracker本身可能留下start/error/finish等观察。

Tracker默认不记录每次evaluation；打开会记录局部context及它从hook参数提取的metrics，有实际空间与I/O开销。当前nsgablack公共on_evaluate_end传的是(objectives,violation)元组，Capability原样转发，Tracker用getattr(feedback,"metrics",{})提取，因此此控制路径的evaluate_end.metrics通常为空；不能据记录条数宣称已保存富ML指标。真实指标应从正式TrainerResult/FeedbackBatch读取。_safe_payload把数组转list、不认识的对象转repr，不是脱敏器或可恢复对象codec；不要在本地上下文中放凭据或巨型对象。ResourceAuditCapability仅保存资源context/报告摘要，不验证全局lease，也不会替代Project的resource_binding_audit。

**怎样判断接对：** events.json含本次run_id、唯一run_name、fit_start/step_end/fit_end、resource_audit的实际授权；events.html展示相同记录。三步预算不保证一定有三条已提交step_end，失败/空步不算逻辑代。正式ModelRef由下一节读取；HTML/SQLite不属于权威模型或checkpoint，也不能从随机record_id或run_name推导Candidate token。

**运行入口：** 保存下一节入口，在副本根 `python run_project.py --check --build-check`，再 `python run_observation_and_report.py`。默认build-check不会建SQLite；变体选择sqlite后，构造SQLiteExperimentStore会在装配阶段初始化schema，需要主动接受这个实际副作用。本轮没有执行这些命令。

### 变体：持久记录并打开送评观察

**目的：** 运行后按事件/步数查询。**改在哪里：** config.py完整替换如下。

```python
STORE_KIND = "sqlite"
RECORD_EVALUATIONS = True
```

**行为变化：** 启用本地SQLite与evaluate_end记录；用唯一run_name隔离本次观察。**限制：** 不提供步骤事务回滚/Exactly-once；supports_resume声明不意味着store可随checkpoint恢复。恢复后重复生命周期可能再写记录；它是审计观察，不能充当EvaluationEvidenceJournal。

## observation.run

完整Project根 `run_observation_and_report.py`。只从一次正式返回值读模型与运行身份，观察文件和权威ModelRef分开核对。

```python
import json
from pathlib import Path
from blackbase.types import TrainerResult
from mlblack.project.project_runner import execute_project

def main():
    run = execute_project(Path(__file__).resolve().parent)
    case = next(x for x in run.case_results if x.request.case_name == "linear_point")
    case.raise_for_failure()
    result = TrainerResult.from_dict(case.output)
    if result.best_feedback is None or result.best_model_ref is None:
        raise RuntimeError("expected evaluated model and published reference")
    print(json.dumps({"run_id": run.run_id,
        "objectives": result.best_objectives.tolist(),
        "model_ref": result.best_model_ref.as_dict()}, ensure_ascii=False, indent=2))
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

## observation.query

**什么时候用：** 已经显式使用上一例SQLite变体，想筛选本次运行的step_end并导出HTML；query_experiments不是SQL控制台，也不重新训练模型。

**先准备什么：** 上例真实运行后留下的数据库和events.json，本次run_name在JSON里。默认memory主例没有数据库，不能凭空查询。标准库SQLite即可；本轮没有访问数据库。

**放在哪：** Project根新增 `inspect_observations.py`。页面由本地export_experiment_html写出，没有开HTTP服务、浏览器自动上传或权限系统。

**接入步骤：** 完整文件如下。先拒绝缺失文件，避免query_experiments内部SQLiteExperimentStore初始化出一个空数据库后误以为“查询无结果”。

```python
import json
from pathlib import Path
from mlblack.catalog.experiment.query import ExperimentQuery, query_experiments
from mlblack.catalog.experiment.dashboard import export_experiment_html

def main():
    root = Path(__file__).resolve().parent/"results"/"observations"
    db = root/"experiments.sqlite3"
    if not db.is_file():
        raise FileNotFoundError("run the explicit sqlite variant first")
    run = json.loads((root/"events.json").read_text(encoding="utf-8"))
    result = query_experiments(str(db), ExperimentQuery(run_name=run["run_name"],
        event="step_end", min_step=0, limit=20))
    (root/"query.json").write_text(json.dumps(result.as_dict(), ensure_ascii=False,
        allow_nan=False, indent=2), encoding="utf-8")
    export_experiment_html(root/"selected_events.html", result.records)

if __name__ == "__main__":
    main()
```

**怎样判断接对：** query.json仅有给定run_name的step_end与实际step，facets按**过滤后且limit后的记录**统计。当前query先list整个运行到内存，再用Python过滤，limit不是SQL分页，也不是取最新20条：结果按rowid升序取前20。payload_contains是区分大小写的字典字符串子串匹配，不是结构化JSON过滤。export的HTML转义文本，但没有登录或授权；分享文件前自行选择内容。

**运行入口：** 上例显式SQLite运行成功后，在同Project根 `python inspect_observations.py`。这是读取已有观察的命令，不调用fit/run_project。SQLiteExperimentStore构造仍执行CREATE IF NOT EXISTS/schema初始化，并非严格read-only连接；生产只读库权限下可能不适用，不能把名字query理解成无写打开。

### 变体：仅查看结束通知

**目的/改在哪里：** 完整替换inspect_observations.py如下，查询fit_end且删除min_step过滤（结束通知step为None）：

```python
import json
from pathlib import Path
from mlblack.catalog.experiment.query import ExperimentQuery, query_experiments
from mlblack.catalog.experiment.dashboard import export_experiment_html

def main():
    root = Path(__file__).resolve().parent/"results"/"observations"
    db = root/"experiments.sqlite3"
    if not db.is_file():
        raise FileNotFoundError("run the explicit sqlite variant first")
    run = json.loads((root/"events.json").read_text(encoding="utf-8"))
    result = query_experiments(str(db), ExperimentQuery(
        run_name=run["run_name"], event="fit_end", limit=20))
    export_experiment_html(root/"finish_events.html", result.records)

if __name__ == "__main__":
    main()
```

**行为变化：** 查询同一run_name的结束观察；HTML条目减少。**限制：** fit_end仍发生于正式finalization之前，不能据此认定模型发布成功。应另外核对正式Case终态和ModelRef。

来源：mlblack `core/capability.py`、`capabilities/tracking.py`、`capabilities/resource_audit.py`、`catalog/experiment/query.py`、`catalog/experiment/dashboard.py` 与共享Plugin生命周期。
