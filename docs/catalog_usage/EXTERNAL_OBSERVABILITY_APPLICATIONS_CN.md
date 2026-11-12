# 外部观察：MySQL 实验索引与 OpenTelemetry 轨迹

下面两种接线各使用一个独立 Project 副本。它们观察同一正式求解过程，不增加优化算法或私有运行器。正文经本地源码核对，未连接数据库、Collector、模型接口，也未执行求解或生成运行收据。

## observation.shared_case · 两种观察器共用的薄装配

复制完整 `examples/cases/bias_gallery/`，保留 Project 的 default 组、L0、规范 Case 入口及 `cases/bias_gallery/` 包。原 `problem/example_problem.py::SphereProblem(dimension=2)` 是二维平方和、边界 `[-5,5]`、无硬约束。以下路径相对该 Case。新增完整 `adapter/observed_search.py`：

```python
from nsgablack.adapters import NSGA2Adapter
from nsgablack.representation import UniformInitializer, GaussianMutation


def build_adapter():
    return NSGA2Adapter(population_size=12, offspring_size=6,
        initializer=UniformInitializer(-5., 5.), mutator=GaussianMutation(sigma=.3))
```

新增完整 `pipeline/observed_pipeline.py`：

```python
from nsgablack.representation import RepresentationPipeline, ClipRepair


def build_pipeline():
    return RepresentationPipeline(repair=ClipRepair(-5., 5.))
```

完整替换 `build_solver.py`：

```python
from pathlib import Path
from nsgablack.core import ComposableSolver
from .adapter.observed_search import build_adapter
from .pipeline.observed_pipeline import build_pipeline
from .plugins.external_observer import build_plugin
from .problem.example_problem import SphereProblem


def build_solver(run_id=None, *, strategy=None, quickstart=False,
                 resource_context=None, component_overrides=None):
    if strategy not in (None, "", "default", "none") or component_overrides:
        raise ValueError("this guide binds its declared components explicitly")
    solver = ComposableSolver(problem=SphereProblem(dimension=2),
        representation_pipeline=build_pipeline(), adapter=build_adapter(),
        resource_context=resource_context, plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(17)
    solver.set_max_steps(6)
    solver.set_bias_module(None, enable=False)
    solver.add_plugin(build_plugin(Path(__file__).resolve().parents[2] / "results"))
    return solver
```

后续每节提供完整 `plugins/external_observer.py`，不能将两个同名文件叠加。工厂只配置观察器；连接或导出在正式生命周期中发生。资源仍由 Project 发放，Plugin 不申请新的 L0 lease。Project 根的 `python run_project.py --check --build-check` 会构造组件，但不执行求解生命周期；它不证明数据库可达、表可写或 spans 已导出。

## plugin.mysql_run_logger · 运行结束时写一条可查询的实验索引

**什么时候用：** 需要按运行身份集中查找摘要和报告路径，已有可写 MySQL。该插件在 `on_solver_finish` 连接并插入一条记录，**不是每代写一次**。它不把候选池、模型或本地报告文件上传到数据库，也不是 Catalog 组件事实数据库的同步器。

**先准备什么：** 使用共用节的独立 Project 副本。安装源码支持的一个驱动 `mysql-connector-python` 或 `pymysql`，准备一个已存在的数据库和账户。插件可以创建表，不能创建数据库；账户需目标表的建表/INSERT 权限，默认打印摘要还需 SELECT。当前驱动连接没有通过这个 Config 提供完整 TLS 选项，不将示例自动视为跨公网数据库部署方案。

运行环境中显式设置 `EXPERIMENT_DB_HOST`、`EXPERIMENT_DB_NAME`、`EXPERIMENT_DB_USER`、`EXPERIMENT_DB_PASSWORD`；可选 `EXPERIMENT_DB_PORT`。这是 Case 自己的运行环境约定，不是写进共享 ContextStore 的新键。不要把密码放在源码、CLI 参数、报告或 Catalog 示例中。下方工厂会检查变量存在，不打印其值；本轮没有读取这些变量。

**放在哪：** 保存共用 builder/Adapter/Pipeline，新增以下完整 `plugins/external_observer.py`。数据库与表名不要取自候选或不受信任的用户文本；这里表名固定为 `experiment_runs`。

**接入步骤：**

```python
import os
from nsgablack.plugins import MySQLRunLoggerConfig, MySQLRunLoggerPlugin


class CaseRunLogger(MySQLRunLoggerPlugin):
    def on_solver_finish(self, result):
        value = dict(result)
        value["run_id"] = self.solver.run_session.run_id
        return super().on_solver_finish(value)


def build_plugin(output_dir):
    del output_dir
    config = MySQLRunLoggerConfig(
        host=os.environ["EXPERIMENT_DB_HOST"],
        port=int(os.environ.get("EXPERIMENT_DB_PORT", "3306")),
        database=os.environ["EXPERIMENT_DB_NAME"],
        user=os.environ["EXPERIMENT_DB_USER"],
        password=os.environ["EXPERIMENT_DB_PASSWORD"],
        table="experiment_runs", connect_timeout=5, print_latest_summary=True,
    )
    return CaseRunLogger(config=config)
```

这个小型 Case 包装只从 RunSession 把真实运行身份放进本次日志参数，不产生新身份，也不修改最终结果权威。基类的 `_get_run_id` 只查 result/artifact 及少量旧字段；不能假定一个从未设置的 `solver.run_id` 总是存在。基类会先 `CREATE TABLE IF NOT EXISTS`，再 INSERT 并 commit，最后可查询刚插入的 id；连接失败不会退回另一个驱动重试错误账户。优先导入 mysql.connector，只有驱动导入不可用才尝试 pymysql。

`summary_json` 存储 status/steps/best 和 artifact_paths 摘要，`extra_json` 存储传入结果的 JSON 化副本；modules_path/bias_path 只有结果 artifacts 提供对应路径字段才有值，插件不检查文件是否存在、可读或已经上传。路径仍可能只在原运行主机可读，本例不额外启用 ModuleReport/BiasReport，不伪造两个路径。best_objective 非标量时，独立 DOUBLE 列可为空，以 JSON 中实际内容为准。

**怎样判断接对：** 正常运行时控制台应出现 `[mysql-run] id=... run_id=...`。在数据库管理工具中读取以下真实表结构对应的字段，按控制台本次 run_id 与 id 核对，不按“最后一行”推断自己的运行。summary_json 和 extra_json 是 TEXT，按 JSON 解析后再读取，不假定数据库列自动支持 JSON 类型。

```sql
SELECT id, run_id, status, steps, best_objective,
       modules_path, bias_path, summary_json, extra_json, created_at
FROM experiment_runs
ORDER BY id DESC LIMIT 5;
```

表没有 run_id 唯一约束，当前实现也没有 upsert；重复 finishing 调用可插入重复行。记录发生在 finishing，早于 teardown 和正式结果最终发布，之后仍可能失败。所以即使行内 status 显示成功，它也只是当时观察，不是权威成功收据；应和正式 Case 终态对账。本例 `plugin_strict=True`，日志失败会作为运行通知错误传播，但此前已提交步骤和求值成本不回滚；不能把它改口说成从未求解。

**运行入口：** 在 Project 副本根，先通过共用节的构建检查，再执行 `python run_project.py`。这条命令实际求解并写数据库；本轮未执行。为了查日志而再次执行它会产生新运行，不是刷新原行。

### 变体一：只写记录，不查询打印摘要

**目的：** 用不要求 SELECT 的写入模式减少额外往返，但不改变记录内容或插入时机。

**改在哪里：** 在同文件追加以下完整包装，保留 CaseRunLogger 和原 build_plugin。

```python
_build_default_plugin = build_plugin


def build_plugin(output_dir):
    plugin = _build_default_plugin(output_dir)
    plugin.cfg.print_latest_summary = False
    return plugin
```

**行为变化：** INSERT/commit 仍执行，默认 `[mysql-run]` 查询摘要不再打印。通过有查询权限的独立管理会话读表；不要将“控制台无摘要”误判为未插入。登录账户是否有建表/写入权限仍需单独核对。

**限制：** 这不提供重试、去重、连接池或最终发布事务，也不会自动管理已有表的 schema 升级。数据库观察有 I/O、锁与空间成本；Plugin 的 observe 角色不代表这些成本为零。

来源：`plugins/storage/mysql_run_logger.py`、共用标准 Project 与 `core/state/run.py`。以上没有实际数据库写入验证。

## plugin.otel_tracing · 先在本地控制台看调用，再考虑 Collector

**什么时候用：** 希望观察求值、根 Adapter 的 propose/update 与插件事件的耗时和异常。它跟踪调用跨度，不是每个候选的数学解释、完整嵌套 Adapter 图或确定性回放日志。

**先准备什么：** 共用节的另一份独立 Project 副本；当前框架与 NumPy，以及 `opentelemetry-api`、`opentelemetry-sdk`。使用独立 Python 运行进程；本地已有全局 TracerProvider 时，插件不能保证再次配置会覆盖它。主例只导出控制台，不配置 Collector。代码显式拒绝当前插件会读取的 `OTEL_EXPORTER_OTLP_ENDPOINT` 环境变量，避免“空 endpoint”意外落入环境回退。

**放在哪：** 保留共用三份文件，新增以下完整 `plugins/external_observer.py`。这个 Case 级子类只额外保存基类已经生成的观察摘要，不重新实现追踪或求解。

**接入步骤：**

```python
import json
import os
from pathlib import Path
from nsgablack.plugins import OpenTelemetryTracingConfig, OpenTelemetryTracingPlugin


class TraceReport(OpenTelemetryTracingPlugin):
    def __init__(self, output):
        super().__init__(config=OpenTelemetryTracingConfig(
            service_name="local-sphere", service_version="case-v1",
            configure_provider=True, console_export=True, otlp_http_endpoint="",
            trace_evaluate=True, trace_adapter=True, trace_plugin_events=True,
        ))
        self.output = Path(output)

    def on_solver_finish(self, result):
        super().on_solver_finish(result)
        self.payload = dict(result["artifacts"]["otel_tracing"])
        self.payload["run_id"] = self.solver.run_session.run_id

    def on_solver_finalized(self, result):
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(json.dumps(self.payload, ensure_ascii=False,
            allow_nan=False, indent=2), encoding="utf-8")


def build_plugin(output_dir):
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip():
        raise ValueError("this local console example requires no OTLP endpoint")
    return TraceReport(Path(output_dir) / "otel.json")
```

基类在 init 配置 tracer，包装 Solver 的两个求值入口、当前根 Adapter 的 propose/update，以及 PluginManager.trigger。复合 Adapter 的每个孩子不会因此自动各得独立跨度；批量求值与内部单点评估也可能形成不同数量的调用。finishing 时恢复包装方法，再把 enabled/spans_emitted/service_name/endpoint 等写入 result.artifacts.otel_tracing。这里在其后复制该摘要，成功 finalized 后才写本地副本。

**怎样判断接对：** 先核对本次 Case 终态及 `results/otel.json` 的 run_id、service_name、console_export。enabled=false 表示 tracing 没有启用；enabled=true 与 spans_emitted>0 只说明取得 tracer 并进入包装，不证明 SDK 真实采样、处理队列和导出成功。应在控制台同时找到实际跨度，例如 `solver.evaluate_population`、`adapter.propose`，并核对 attributes.method/component。插件默认用 BatchSpanProcessor，摘要不是导出回执；没有在 finishing 显式 force_flush/shutdown，不能凭 JSON 宣布所有跨度已经送达。

**运行入口：** Project 副本根执行 `python run_project.py --check --build-check`，再执行 `python run_project.py`。第一条不会触发 init 里的真实 SDK 配置；第二条会求解和输出控制台 spans。本轮未运行。缺 API 会警告并禁用，SDK 设置失败可能沿用当前 Provider，不因构建成功就推断后端正常。

### 变体一：保留评估轨迹，关闭 Adapter 和插件分派跨度

**目的：** 对主要成本在 Problem 求值的 Case，减少追踪事件数量，仍观察求值入口。

**改在哪里：** 在本节模块末尾追加这个包装，保留 TraceReport 及默认工厂。

```python
_build_full_plugin = build_plugin


def build_plugin(output_dir):
    plugin = _build_full_plugin(output_dir)
    plugin.cfg.trace_adapter = False
    plugin.cfg.trace_plugin_events = False
    return plugin
```

**行为变化：** init 只包装 evaluate_individual/evaluate_population，不再主动增加 adapter.propose/update 与 plugin.trigger 跨度。不承诺 spans 数量按某个固定比例下降，也不把跨度数量当成候选求值次数。

**限制：** 关闭部分跨度不会撤销已有全局 Provider 或其它库自己产生的 spans。插件源码只在正常 finish 恢复这些包装，不能据本例声称已证明任意 init/异常中断路径都能完整清理；也不保证多 Case 并发隔离。需要跨进程 Collector、采样策略和严格导出保证时，应明确设计共享 tracing 运行配置与回执，而不是把空 endpoint 当成已部署。

来源：`plugins/ops/otel_tracing.py` 与本页共用正式 Case；仅源码与接线核对。
