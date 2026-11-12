# 运行插件：在正式 Case 中接线、观察与恢复

本文以现有 `examples/cases/assembly_workbench` Project 的 `cases/hybrid_search` 为宿主。每节可以独立应用；代码都是明确的新文件或现有 builder 的修改点。Project 继续负责 L0 授权，Case 继续使用原 Problem、Pipeline、Adapter、Bias、预算和标准入口。本文只按源码整理接线与预期，不提供执行结果。

## plugin.checkpoint_resume · 保存可恢复状态，并从已有提交点继续

**什么时候用：** 长任务需要从已提交逻辑步继续，或要保存正式 Case 的最终状态。它恢复 Solver、Adapter、池、声明的组件与 RNG 状态；不是只重新填一个种群数组。周期检查点和最终权威检查点的发布方式不同，必须分别读取。

**先准备什么：** 使用 `assembly_workbench/cases/hybrid_search`；其 `build_solver.py` 已有一个 `CheckpointResumePlugin`，本例替换该注册，不再追加第二个。现有 `output` 来自 `HybridConfig.output_dir`，默认是 Project 下 `results/hybrid_search`；`settings.checkpoint_every` 来自同一配置。候选、反馈、Unit 都由原宿主管理，不传给本工厂。准备一个仅供本应用保管、恢复时仍能取得的非空 `NSGABLACK_CHECKPOINT_HMAC_KEY`；只恢复本应用受控目录内自生成、未被替换的文件。`trusted_roots` 限定路径，HMAC 与 `strict=True` 校验载荷来源和完整性；外层 pickle 在 HMAC 校验前就会反序列化，不能让任意外来 `.pkl` 变得安全。

**放在哪：** 新增 `examples/cases/assembly_workbench/cases/hybrid_search/plugins/checkpoint_recipe.py`。下面只扩展已有 `on_solver_finalized` 通知来输出读取审计，先调用原插件实现；恢复、冻结与最终发布仍由原插件和共享生命周期完成。

**接入步骤：** 新文件完整内容如下。`resume` 是装配配置，不在运行中修改它。新的 `checkpoint_recipe` 目录避免混用原示例目录中的旧组件配置。

```python
from pathlib import Path
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.utils.engineering.file_io import atomic_write_json


class CaseCheckpoint(CheckpointResumePlugin):
    def on_solver_finalized(self, result):
        super().on_solver_finalized(result)
        atomic_write_json(
            Path(self.cfg.checkpoint_dir) / "resume_report.json",
            self.get_report(), ensure_ascii=False, indent=2, encoding="utf-8",
        )


def attach_checkpoint(solver, output, *, every, resume=False):
    root = (Path(output) / "checkpoint_recipe").resolve()
    plugin = CaseCheckpoint(config=CheckpointResumeConfig(
        checkpoint_dir=str(root), save_every=every, save_on_finish=True,
        keep_last=3, auto_resume=resume, resume_from="latest", strict=True,
        trusted_roots=(str(root),), restore_plugin_state=True,
        restore_rng_state=True,
    ))
    solver.add_plugin(plugin)
    return plugin
```

在原 `build_solver.py` 增加以下导入，把原来整段 `solver.add_plugin(CheckpointResumePlugin(...))` 替换成此调用。位置仍在 Provider 分支后、`WorkbenchTrace` 前；保留 `apply_solver_component_overrides(solver, overrides)` 和 `return solver`。删去不再使用的旧 checkpoint 导入。

```python
from .plugins.checkpoint_recipe import attach_checkpoint

# 位于 build_solver() 内：solver/output/settings 都由原 builder 建立。
attach_checkpoint(solver, output, every=settings.checkpoint_every, resume=False)
```

`save_every` 按已提交逻辑步计数，不按物理尝试或候选数计数。周期文件是本地签名 `.pkl`。`save_on_finish` 先冻结状态，最终检查点要等 teardown 和所有严格 finalization prepare 成功，再随 Case 发布事务提交；不能把 `on_solver_finish` 已被调用当作成功。

**怎样判断接对：** 先看标准 Project 是否成功结束，再读取 `results/hybrid_search/checkpoint_recipe/resume_report.json`：`last_saved_generation` 是保存的代数标记；恢复时看 `last_loaded_path`、`last_loaded_generation` 和 `resume_audit.status/current/issue_count/trajectory_equivalent`。`queued` 只表示排队，尚未应用；无问题的已应用恢复应是 `restored`、`current=True`、`issue_count=0`。首次新运行的 `not_attempted` 正常。不要仅看目录里有文件。

宿主原有 `results/hybrid_search/trace.json` 的 `final.checkpoint` 记录最终引用。标准 Case 下它通常是 Artifact URI，来源是带 `case_finalization_sealed=True` 的 `checkpoint_final` 发布收据；不是承诺在本地再写一个最终 `.pkl`。结果中的 `checkpoint_latest_ref` 是引用描述。周期本地文件由 `keep_last` 保留；本例 `resume_from="latest"` 搜索本地周期文件，不会自动下载该 Artifact URI。

**运行入口：** 从 nsgablack 仓库根目录，用保存好上述密钥的同一环境运行；不要每次恢复前生成新密钥。`--group hybrid` 只选此 Case，未指定 group 会走 Project 的其它场景。

```powershell
python examples/cases/assembly_workbench/run_project.py --group hybrid
```

### 变体一：从本地最后一个周期检查点恢复未完成计划

**目的：** 进程中断后续接原有限 SearchPlan，而不是从初始候选重新搜索。

**改在哪里：** 保持上述类、候选配置、预算、插件集合和密钥一致，只把 builder 中调用改成以下内容，然后运行同一个 Project 命令。运行前确认 `checkpoint_recipe` 内已有本应用产生、仍可读取的周期 `.pkl`；严格模式不会把缺失检查点伪装成一次成功恢复。

```python
# 替换 build_solver() 中原 attach_checkpoint 调用。
attach_checkpoint(solver, output, every=settings.checkpoint_every, resume=True)
```

**行为变化：** 原插件在 `prepare_restore` 中请求恢复，交由既有恢复信封在 setup 后应用；普通初始化钩子看到的是恢复后状态。本节的审计文件在最终发布通知后写出，读取方法同上。恢复的是已有进度和剩余工作，不会自动赠送新的 `max_steps`、求值预算，也不会重开一个已完成的有限计划。

**限制：** `latest` 是本地保留文件中的最新者，不一定是原进程最后执行的步骤。最终 Artifact 引用不能直接冒充本插件的本地路径参数。该扩展类的审计文件是观察输出；单独存在的旧审计不能证明本次恢复成功。不要手动重排 setup、初始化或直接向 Adapter 填恢复状态。

来源：[插件配置、恢复与发布](../../plugins/system/checkpoint_resume.py)、[正式宿主 builder](../../examples/cases/assembly_workbench/cases/hybrid_search/build_solver.py)、[宿主 trace 与权威引用读取](../../examples/cases/assembly_workbench/cases/hybrid_search/plugins/trace.py)、[Project 分组](../../examples/cases/assembly_workbench/project_config.py)。配套 key：`plugin.module_report`、`plugin.profiler`。

## plugin.module_report · 记录实际装配清单与 Bias 统计

**什么时候用：** 改装配后想核对实际绑定了什么 Solver、根 Adapter、Pipeline 和 Plugin；或要把已有 Bias 的累计统计交给报告消费者。它不负责证明算法更好，也不会由一个配置标签自动还原全部嵌套组件图。

**先准备什么：** 使用正式 `assembly_workbench/cases/hybrid_search`。原 builder 已建立 `solver`、输出目录 `output` 和 `settings`；仍保留原 checkpoint 与 `WorkbenchTrace`。不需要提供种群矩阵或自行构造 Unit。报告默认覆盖同名文件，本例用 `hybrid` 作为人工文件标签，不把它叫作 Solver 权威运行身份。

**放在哪：** 新增 `examples/cases/assembly_workbench/cases/hybrid_search/plugins/module_report_recipe.py`。下面工厂由该 Case 的 `build_solver.py` 调用，读取函数可供项目外的只读报告脚本导入。

**接入步骤：** 新文件完整内容如下。

```python
import json
from pathlib import Path
from nsgablack.plugins import ModuleReportConfig, ModuleReportPlugin


def attach_module_report(solver, output):
    plugin = ModuleReportPlugin(config=ModuleReportConfig(
        output_dir=str(Path(output) / "module_report"),
        run_id="hybrid", write_bias_markdown=True,
    ))
    solver.add_plugin(plugin)
    return plugin


def read_module_report(directory, label="hybrid"):
    directory = Path(directory)
    modules = json.loads((directory / f"{label}.modules.json").read_text(encoding="utf-8"))
    biases = json.loads((directory / f"{label}.bias.json").read_text(encoding="utf-8"))
    return {
        "solver": modules["solver"]["class"],
        "root_adapter": modules["adapter"]["class"],
        "pipeline": modules["pipeline"],
        "plugins": modules["plugins"],
        "bias_enabled": biases["enabled"],
        "bias_statistics": biases.get("biases", []),
    }
```

在原 `build_solver.py` 增加导入，并在原 `solver.add_plugin(WorkbenchTrace(...))` 后、`apply_solver_component_overrides(...)` 前加入调用；原来的 `return solver` 继续返回这个已挂载报告插件的 Solver。

```python
from .plugins.module_report_recipe import attach_module_report

# 位于原 build_solver() 内，output 使用原 Case 的解析结果。
attach_module_report(solver, output)
```

运行时 `on_solver_init` 建立输出目录，`on_solver_finish` 收集实际状态并写入三份报告；不为观察创建 Unit，不接管候选生成或反馈。报告写入 `result["artifacts"]` 的是本地路径字符串，不是本插件发放的权威 Artifact 收据。

**怎样判断接对：** 在默认 `results/hybrid_search/module_report` 下读取 `hybrid.modules.json`、`hybrid.bias.json`、`hybrid.bias.md`。前者的 `plugins` 应包含本次实际挂载的 `module_report`，`adapter.class` 是根组合 Adapter，而非承诺列出每个叶算法。更完整的本宿主树见原有 `trace.json` 的 `components`。

Bias JSON 的 `enabled`、`biases`、`total_contribution` 来自当前 Bias 统计；每项的 `usage_count/weight/total_contribution` 以具体 Bias 提供的统计为准。它们表示调用与累计贡献，不是原始 Problem 目标，也不是对最终解的因果归因。即使文件已写出，后续 teardown 或严格发布仍可能失败，成功状态须看标准 Project/Case 结果。

**运行入口：** 从仓库根目录运行下面真实分组。之后把绝对或相对报告目录传给上面的 `read_module_report`；它只读 JSON，不启动 Solver。

```powershell
python examples/cases/assembly_workbench/run_project.py --group hybrid
```

### 变体一：按正式运行身份分文件，保留多次装配审计

**目的：** 连续运行不同装配后仍能逐份比较，而不被固定 `hybrid` 标签覆盖。

**改在哪里：** 将同一个 `module_report_recipe.py` 完整替换为以下内容；builder 中导入与调用保持原样。现有初始化钩子此时已有 `run_session.run_id`，直接用它作文件标签；不在 builder 阶段猜将来的运行身份。

```python
from pathlib import Path
from nsgablack.plugins import ModuleReportConfig, ModuleReportPlugin


class PerRunModuleReport(ModuleReportPlugin):
    def on_solver_init(self, solver):
        self.cfg.run_id = str(solver.run_session.run_id)
        return super().on_solver_init(solver)


def attach_module_report(solver, output):
    plugin = PerRunModuleReport(config=ModuleReportConfig(
        output_dir=str(Path(output) / "module_report"),
        write_bias_markdown=False,
    ))
    solver.add_plugin(plugin)
    return plugin
```

**行为变化：** JSON 文件名变为 `<实际run_id>.modules.json` 和 `<实际run_id>.bias.json`。`metadata.run_id` 可与宿主 `trace.json.run_id` 对齐，再比较各次 `plugins/pipeline/biases`；不再生成新的 Bias Markdown。这个变体的完整替换文件不包含前面的读取函数，使用普通 UTF-8 JSON 读取即可。

**限制：** 插件没有目录保留清理策略；由应用安排历史文件管理。恢复同一个运行身份时仍可能重写对应文件；已有旧 `.bias.md` 不会因关闭开关自动删除。模块清单与统计仍是观察报告，不拥有最终候选或发布授权。

来源：[配置、清单与 Bias 字段](../../plugins/ops/module_report.py)、[正式 builder](../../examples/cases/assembly_workbench/cases/hybrid_search/build_solver.py)、[宿主组件树](../../examples/cases/assembly_workbench/cases/hybrid_search/plugins/trace.py)。配套 key：`plugin.checkpoint_resume`、`plugin.profiler`、`plugin.decision_trace`。

## plugin.profiler · 分清逻辑提交耗时与失败、空闲尝试

**什么时候用：** 需要知道每个已提交步骤的墙钟耗时、消耗的求值行数，以及未提交尝试是否占用时间。它适合解释标准 Case 的运行节奏；不是 CPU/GPU 采样器，不会自动分离出纯 Problem 数值计算时间。

**先准备什么：** 使用 `assembly_workbench/cases/hybrid_search`，保留其标准 builder、预算、`WorkbenchTrace` 与 checkpoint。工厂接收该 builder 的 `solver/output`，没有隐含候选或 feedback 参数。基线固定文件标签为 `hybrid`，显式 `overwrite=True` 表示重复运行会替换旧 profile；默认配置实际是 `overwrite=False`，同名文件存在会在初始化时报错。

**放在哪：** 新增 `examples/cases/assembly_workbench/cases/hybrid_search/plugins/profiler_recipe.py`，由现有 `build_solver.py` 调用。

**接入步骤：** 新文件完整内容如下。`flush_every=2` 启用每两条已提交记录的中间刷新，便于观察长任务；它不是每两次物理尝试刷新。

```python
import json
from pathlib import Path
from nsgablack.plugins import ProfilerConfig, ProfilerPlugin


def attach_profiler(solver, output):
    plugin = ProfilerPlugin(config=ProfilerConfig(
        output_dir=str(Path(output) / "profile"),
        run_id="hybrid", overwrite=True, flush_every=2,
    ))
    solver.add_plugin(plugin)
    return plugin


def read_profile(path):
    profile = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        "summary": profile["summary"],
        "attempts": [(row["attempt"], row["status"], row["eval_delta"])
                     for row in profile["per_attempt"]],
        "committed": [(row["generation"], row["wall_s"], row["eval_delta"])
                      for row in profile["per_generation"]],
        "eval_count": profile["eval_count"],
    }
```

在原 `build_solver.py` 增加以下导入；在 `WorkbenchTrace` 注册后、`apply_solver_component_overrides(...)` 前调用工厂，保留原 `return solver`。

```python
from .plugins.profiler_recipe import attach_profiler

# 位于原 build_solver() 内。
attach_profiler(solver, output)
```

插件在每个 `on_step_attempt_start/end` 测量墙钟和 `solver.evaluation_count` 差值。所有已结束尝试进入 `per_attempt`；只有 committed 尝试进入 `per_generation`。求值即使未导致逻辑提交也可能消耗预算，不能只加后者估算全程求值。`plugins_profile` 消费 PluginManager 已有的事件计时，不是各算法函数的调用树。

**怎样判断接对：** 默认文件为 `results/hybrid_search/profile/hybrid.profile.json`。先读取 `summary.attempts`、`attempt_status_counts`、`generations`，再把 `per_attempt[].status/committed/eval_delta` 与 `per_generation` 对照；不要假设两张列表一样长。`wall_s` 是该尝试的墙钟时间，`eval_per_s` 按它与求值差值计算；`phase` 是已有 Adapter 运行投影的可用阶段标签，允许为空。顶层 `eval_count` 是 Solver 累计计数，恢复运行时也不能只用本次记录推算它。

`final=True` 表示插件收到 finishing 通知并写了一次报告，不表示 Case 已通过严格发布。`result.artifacts.profile_json` 是本地观察文件路径；权威成功和最终解仍以标准 Case 的提交结果为准。

**运行入口：** 从仓库根目录使用现有 Project 分组。

```powershell
python examples/cases/assembly_workbench/run_project.py --group hybrid
```

### 变体一：分别测量原 Problem 路径与正式 Provider 路径

**目的：** 宿主已有 `RecipeProvider`，用同一搜索装配比较两条评估接线的计数与墙钟，不把“配置里写了 provider”当作已经启用。

**改在哪里：** 将 `profiler_recipe.py` 完整替换成下面内容，builder 调用保持不变。标签在运行初始化时取正式身份，防止第二次覆盖第一次。

```python
from pathlib import Path
from nsgablack.plugins import ProfilerConfig, ProfilerPlugin


class PerRunProfiler(ProfilerPlugin):
    def on_solver_init(self, solver):
        self.cfg.run_id = str(solver.run_session.run_id)
        return super().on_solver_init(solver)


def attach_profiler(solver, output):
    plugin = PerRunProfiler(config=ProfilerConfig(
        output_dir=str(Path(output) / "profile"),
        overwrite=False, flush_every=2,
    ))
    solver.add_plugin(plugin)
    return plugin
```

然后分别使用真实存在的两个 Project 分组；`provider` 在 `project_config.py` 通过 `component_overrides` 把 `evaluation_mode` 改为 `provider`，原 builder 的条件分支据此实际注册 `RecipeProvider`。

```powershell
python examples/cases/assembly_workbench/run_project.py --group hybrid
python examples/cases/assembly_workbench/run_project.py --group provider
```

**行为变化：** 得到两份 `<run_id>.profile.json`。每次运行后记录该 ID，并读取当次 `trace.json`：其 `components` 可核对实际 Provider，`records[].evaluations/problem_calls` 可区分 Solver 行计数与 Problem 调用。再比较相同范围的 profile 尝试、提交与耗时；不要预先许诺 Provider 更快。

**限制：** 墙钟会受机器负载和其它插件影响，不是隔离性能结论。宿主固定 `trace.json` 会由后一次成功运行覆盖，需先读出前一次记录。恢复同一身份且旧 profile 尚在时，`overwrite=False` 会拒绝覆盖；此时应有意识地选择另一输出目录或覆盖策略。

来源：[Profiler 尝试与提交记录](../../plugins/ops/profiler.py)、[真实 Provider 启用分支](../../examples/cases/assembly_workbench/cases/hybrid_search/build_solver.py)、[Project 的 hybrid/provider 分组](../../examples/cases/assembly_workbench/project_config.py)、[宿主观察字段](../../examples/cases/assembly_workbench/cases/hybrid_search/plugins/trace.py)。配套 key：`plugin.module_report`、`plugin.decision_trace`。

## plugin.decision_trace · 读调用事件，再为应用补充明确的观察理由

**什么时候用：** 排查提案、评估、更新和插件通知的先后，或需要应用显式记录一条有 reason/evidence 的事件。默认 trace 记录方法调用边界，不会自动解释 NSGA 的每次选择理由，也不保存重新执行算法所需的完整候选、反馈和 RNG 状态。

**先准备什么：** 使用正式 `assembly_workbench/cases/hybrid_search`；沿用原 `solver/output`、Problem、Adapter 和正式提交过程。基线打开真实的 `capture_evaluate/capture_adapter/capture_plugin_events` 分支。输出会包含调用异常的消息，作为应用诊断文件管理，不将它当作候选仓库或凭据存储。

**放在哪：** 新增 `examples/cases/assembly_workbench/cases/hybrid_search/plugins/decision_trace_recipe.py`；由现有 builder 调用。下面读取函数只消费文件，不运行搜索。

**接入步骤：** 新文件完整内容如下。

```python
from pathlib import Path
from nsgablack.plugins import DecisionTraceConfig, DecisionTracePlugin
from nsgablack.utils.runtime.decision_trace import DecisionReplayEngine


def attach_decision_trace(solver, output):
    plugin = DecisionTracePlugin(config=DecisionTraceConfig(
        output_dir=str(Path(output) / "decision_trace"), run_id="hybrid",
        overwrite=True, flush_every=1,
        capture_evaluate=True, capture_adapter=True,
        capture_plugin_events=True, include_context_events=True,
    ))
    solver.add_plugin(plugin)
    return plugin


def read_calls(path):
    replay = DecisionReplayEngine.from_jsonl(Path(path))
    return {
        "summary": replay.summary(),
        "adapter_calls": list(replay.iter(event_type="runtime_call", component="adapter.propose")),
        "failed": [row for row in replay.iter() if row["decision"] == "failed"],
    }
```

在原 `build_solver.py` 增加导入，在 `WorkbenchTrace` 后、`apply_solver_component_overrides(...)` 前调用，保留原 `return solver`。

```python
from .plugins.decision_trace_recipe import attach_decision_trace

# 位于原 build_solver() 内；这不是在 propose/update 中临时注册。
attach_decision_trace(solver, output)
```

运行初始化后插件包装 Solver 的两个评估入口、根 Adapter 的 `propose/update`、PluginManager 的 `trigger`。每次被包装调用返回或抛错时立即追加 JSONL；插件事件的名字记录在 `reason_code`。`capture_adapter=True` 只直接包装根 Adapter，不等于自动递归包装每个叶 Adapter。运行结束时恢复这些方法包装并写 summary。

**怎样判断接对：** 默认读取 `results/hybrid_search/decision_trace/hybrid.decision_trace.jsonl` 与 `hybrid.decision_trace.summary.json`。summary 的 `count/event_type_counts/component_counts/first_seq/last_seq` 是事件统计；逐条看 `seq/component/decision/reason_code/evidence.duration_ms`。一条 `completed` 只说明那个调用正常返回，`update` 返回也不自动等于整个步骤已提交。包装内嵌调用在内层返回时先记录，因此 `seq` 是记录顺序，不是调用开始顺序。

summary 的 `final=True` 和 `result.artifacts.decision_trace_*` 都是 finishing 阶段的观察数据，不能代替 Case 最终发布。`DecisionReplayEngine` 的 replay 是筛选、遍历已有事件；它不会重新执行 Solver，更不能代替 checkpoint 恢复。

**运行入口：** 从仓库根目录运行现有独立分组；读取函数的 `path` 传上述 JSONL 路径。

```powershell
python examples/cases/assembly_workbench/run_project.py --group hybrid
```

### 变体一：只保留每次正式提交的应用观察事件

**目的：** 为大任务减少自动调用日志，并把“实际提交”与“方法返回”分开。应用在已经发生提交的钩子中明确给出观察依据，不替算法编造选择原因。

**改在哪里：** 将 `decision_trace_recipe.py` 完整替换为以下内容；builder 导入和调用不变。`CommitObservation` 是无累计状态的观察 Plugin，使用已有 `on_generation_committed`，不新增运行循环或决定/否决权限。

```python
from pathlib import Path
from nsgablack.plugins import DecisionTraceConfig, DecisionTracePlugin
from nsgablack.plugins.base import Plugin


class CommitObservation(Plugin):
    def __init__(self):
        super().__init__(name="case_commit_observation", priority=20)

    def on_generation_committed(self, generation, outcome):
        self.solver.record_decision_event(
            event_type="case_observation", component="hybrid_search",
            decision="observed_commit", reason_code="generation_committed_hook",
            inputs={"generation": int(generation)},
            evidence={"evaluation_count": int(self.solver.evaluation_count)},
            outcome={"committed": True},
        )


def attach_decision_trace(solver, output):
    trace = DecisionTracePlugin(config=DecisionTraceConfig(
        output_dir=str(Path(output) / "decision_trace"), run_id="hybrid",
        overwrite=True, flush_every=1,
        capture_evaluate=False, capture_adapter=False,
        capture_plugin_events=False, include_context_events=False,
    ))
    solver.add_plugin(trace)
    solver.add_plugin(CommitObservation())
    return trace
```

**行为变化：** 三类自动包装关闭，但 trace 初始化仍安装 `solver.record_decision_event`，每个 committed 通知由观察者调用它追加一条 `case_observation`。记录只包含逻辑代标记和累计求值计数，不复制候选。按 `event_type="case_observation"` 读取即可与原有 `trace.json.records` 的提交记录对照；未提交尝试不会触发这个观察者。

**限制：** 此配置不会记录未提交尝试、调用异常或自动耗时，不能据此声称运行期间没有错误。summary 的周期刷新在 trace 自己的提交钩子执行，可能早于同一通知中观察者的追加；JSONL 已追加的事件与中间 summary 可能暂差一条，finishing summary 才重新汇总。这个完整替换文件不带前面的读取函数，可继续用真实 `DecisionReplayEngine.from_jsonl(...).iter(...)` 做文件消费。

来源：[配置、包装与追加](../../plugins/ops/decision_trace.py)、[事件结构与只读 ReplayEngine](../../utils/runtime/decision_trace.py)、[正式 builder](../../examples/cases/assembly_workbench/cases/hybrid_search/build_solver.py)、[原宿主提交观察者](../../examples/cases/assembly_workbench/cases/hybrid_search/plugins/trace.py)。配套 key：`plugin.profiler`、`plugin.checkpoint_resume`、`plugin.module_report`。
