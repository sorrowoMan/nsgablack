# 观察插件：接进正式 Case，再读取实际产物

每章独立使用当前 `examples/cases/catalog_recipes` Project 的 `cases/composite` Case。先把整个 Project 复制到自己的工作目录，保留 Project→Case→Scaffold 结构；下文路径按仓库原位置标注。一次采用一章的完整 builder，不把四份 builder 依次追加。Project 的 `default` 组已经启用 composite，负责授予 CPU ResourceContext；无需另写运行循环。

以下是按源码核对的装配教学，没有运行本章改装后的算法，也没有生成运行收据。JSON、CSV 和数据库都是本地观察产物；须结合本次标准 Project 的最终状态读取，文件存在不等于成功发布。

## plugin.memory · 看进程内存采样，并明确 GC 实际做了什么

**什么时候用：** 想知道同一 Python 进程在搜索前后及周期清理后的 RSS 如何变化，或排查周期 GC 带来的停顿。该插件调用 `gc.collect()`，并在 Solver 存在 `temp_data` 时调用其 `clear()`；它不回收 SolutionPool 中仍被引用的解，也不会把 NumPy 数组改成低精度。不能保证 RSS 下降。

**先准备什么：** 安装当前 nsgablack、blackbase、NumPy 和可选依赖 psutil。psutil 用于进程采样，缺失时插件安静地跳过采样，结果可能为空。本例沿用 composite Case 的二维 `QuadraticProblem`：每个候选 shape 为 `(2,)`，单目标为平方和，边界由原 Pipeline 修复为 `[-2,2]`。wide/narrow 各维护自己的四成员 Unit；插件不接收成员矩阵。`output` 由下面 builder 根据 Project 路径生成；`solver` 来自正式 starter 工厂。

**放在哪：** 新建 `examples/cases/catalog_recipes/cases/composite/plugins/memory_recipe.py`，并把同一 Case 的 `build_solver.py` 完整替换为下方版本。保留原 `problem/`、`pipeline/`、`run_solver.py`、Project 配置与入口。

**接入步骤：** `plugins/memory_recipe.py` 完整内容如下。子类只增加 finishing 时的 JSON 观察副本，实际采样和清理由现有 MemoryPlugin 执行。

```python
import json
from pathlib import Path
from nsgablack.plugins import MemoryPlugin


class MemoryReport(MemoryPlugin):
    def __init__(self, output, *, enable_auto_gc=True):
        super().__init__(cleanup_interval=1, enable_auto_gc=enable_auto_gc)
        self.output = Path(output)

    def on_solver_finish(self, result):
        super().on_solver_finish(result)
        self.output.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": str(self.solver.run_session.run_id),
            "enable_auto_gc": self.enable_auto_gc,
            "cleanup_interval": self.cleanup_interval,
            "usage": self.get_memory_usage(),
        }
        (self.output / "memory.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def attach_memory(solver, output):
    plugin = MemoryReport(output, enable_auto_gc=True)
    solver.add_plugin(plugin)
    return plugin
```

`cases/composite/build_solver.py` 完整内容：

```python
from pathlib import Path
from nsgablack.project.starter import build_starter_solver
from nsgablack.project import apply_solver_component_overrides
from nsgablack.adapters import CompositeAdapter, NSGA2Adapter
from nsgablack.representation import GaussianMutation
from .problem import build_problem
from .pipeline import build_pipeline
from .plugins.memory_recipe import attach_memory


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = build_starter_solver(problem=build_problem(), pipeline=build_pipeline(),
                                  resource_context=resource_context, max_steps=2)
    solver.set_adapter(CompositeAdapter(adapters=[
        NSGA2Adapter(name="wide", population_size=4, offspring_size=4,
                     mutator=GaussianMutation(sigma=0.4)),
        NSGA2Adapter(name="narrow", population_size=4, offspring_size=4,
                     mutator=GaussianMutation(sigma=0.05)),
    ]))
    output = Path(__file__).resolve().parents[2] / "results" / "memory"
    attach_memory(solver, output)
    apply_solver_component_overrides(solver, component_overrides)
    return solver
```

运行初始化先采样一次；`on_generation_end` 收到满足取模条件的代数时清理并采样，本例间隔为正整数1。finishing 先取一次 `generation="final"` 样本，再做最终清理并采样，所以 final 标签可能重复。不要用样本数推算提交数或求值数。不要把 `cleanup_interval` 设为0，源码直接取模。

**怎样判断接对：** 读取 Project 的 `results/memory/memory.json`，核对本轮 `run_id` 与 `enable_auto_gc=True`。`usage.current_mb` 是最后样本 RSS，`peak_mb` 只是已采样 RSS 最大值，`growth_mb` 是末次减首次；不是操作系统记录的真实峰值。`usage.snapshots` 每行有 `generation/rss_mb/vms_mb`，单位均为 MiB；VMS 不是实占物理内存。`usage={}` 时先核对 psutil，而非把空值当零内存。原插件还把同一列表写入 Solver result 的 `memory_snapshots`，标准 CLI 不保证完整打印它；本例 JSON 才是明确的读取入口。

开启 GC 会暂停本进程，并可能清空宿主自建的 `temp_data`；此 Case 没有依赖该字段传递候选。代码没有接管评估或否决 finalization。文件在 `on_solver_finish` 写入，会覆盖上一次同名文件，也可能先于后续 teardown 失败；需先确认本次 Project 的完成状态。

**运行入口：** 从仓库根目录运行当前标准 Project，输出目录位于该 Project 内。

```powershell
python examples/cases/catalog_recipes/run_project.py --group default
```

### 变体一：保留起止采样，避免主动 GC 和 temp_data 清理

**目的：** 怀疑周期 GC 扰动耗时，希望把它关闭，与基线的进程内存观察作对照，而不是通过改算法搜索强行降低内存。

**改在哪里：** 只完整替换 `memory_recipe.py` 的 `attach_memory` 函数，保留上面的导入与 MemoryReport 类；builder 接线不变。

```python
def attach_memory(solver, output):
    plugin = MemoryReport(output, enable_auto_gc=False)
    solver.add_plugin(plugin)
    return plugin
```

**行为变化：** 不调用插件自己的 `gc.collect()` 或 `temp_data.clear()`。源码在 `_cleanup_memory` 开头返回，因此同时失去周期采样和最终清理后采样，只保留初始化、finishing 两个采样时点。仍由原 `MemoryReport` 写 `memory.json`，其中开关为 False。

**限制：** 不是“同样密度的连续无侵入采样”，也不会关闭 Python 自身的自动 GC。两次独立运行应先保存前一份 JSON，并控制机器负载；不能仅凭更少的峰值样本宣称该配置更省内存。

来源：[MemoryPlugin 实际清理与采样](../../plugins/system/memory_optimize.py)、[正式 Case builder](../../examples/cases/catalog_recipes/cases/composite/build_solver.py)、[Project 实际启用项](../../examples/cases/catalog_recipes/project_config.py)。配套 key：`plugin.profiler`、`plugin.benchmark_harness`。

## plugin.benchmark_harness · 保存统一 CSV，并读清每一列的比较含义

**什么时候用：** 想把同一种 Case 的不同运行交给同一 CSV/JSON 消费程序，记录累计求值量与墙钟，而不是各写一套计数器。它记录数据，不是统计显著性检验或算法排名器。

**先准备什么：** 使用完整 `catalog_recipes/cases/composite` Case；本章独立替换 builder，沿用二维单目标平方和、原 Pipeline 与 wide/narrow 两个 NSGA2 实例。Project 默认只运行这个 Case并提供 CPU 授权。不要自己传 population/objectives 给插件。`BenchmarkHarnessConfig.seed=None` 刻意不重设随机源；若设整数，源码会在初始化调用 `solver.set_random_seed(seed)`，不只是给报告贴标签。真实配置字段是 `output_dir/run_id/seed/log_every/flush_every/overwrite`，没有 `save_population`。

**放在哪：** 新建该 Case 的 `plugins/benchmark_recipe.py`，再完整替换 `build_solver.py`。本章输出位于 Project 的 `results/benchmark/`。

**接入步骤：** `plugins/benchmark_recipe.py`：

```python
import csv
import json
from pathlib import Path
from nsgablack.plugins import BenchmarkHarnessConfig, BenchmarkHarnessPlugin


def attach_benchmark(solver, output):
    plugin = BenchmarkHarnessPlugin(config=BenchmarkHarnessConfig(
        output_dir=str(output), run_id="composite", seed=None,
        log_every=1, flush_every=1, overwrite=True,
    ))
    solver.add_plugin(plugin)
    return plugin


def read_benchmark(output, run_id="composite"):
    output = Path(output)
    with (output / f"{run_id}.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    summary = json.loads((output / f"{run_id}.summary.json").read_text(encoding="utf-8"))
    return {"rows": rows, "summary": summary}
```

`cases/composite/build_solver.py`：

```python
from pathlib import Path
from nsgablack.project.starter import build_starter_solver
from nsgablack.project import apply_solver_component_overrides
from nsgablack.adapters import CompositeAdapter, NSGA2Adapter
from nsgablack.representation import GaussianMutation
from .problem import build_problem
from .pipeline import build_pipeline
from .plugins.benchmark_recipe import attach_benchmark


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = build_starter_solver(problem=build_problem(), pipeline=build_pipeline(),
                                  resource_context=resource_context, max_steps=2)
    solver.set_adapter(CompositeAdapter(adapters=[
        NSGA2Adapter(name="wide", population_size=4, offspring_size=4,
                     mutator=GaussianMutation(sigma=0.4)),
        NSGA2Adapter(name="narrow", population_size=4, offspring_size=4,
                     mutator=GaussianMutation(sigma=0.05)),
    ]))
    output = Path(__file__).resolve().parents[2] / "results" / "benchmark"
    attach_benchmark(solver, output)
    apply_solver_component_overrides(solver, component_overrides)
    return solver
```

初始化打开 CSV 并写表头；只有 `on_generation_committed` 满足 `generation % log_every == 0` 才追加行。`flush_every=1` 每行刷新文件，但不代表每行生成权威结果收据。finishing 再写 summary 并关闭 CSV，把路径加入 result 的 `artifacts.benchmark_csv/benchmark_summary_json`。

**怎样判断接对：** 读取 `results/benchmark/composite.csv` 和 `composite.summary.json`，或把该目录传给上面的 `read_benchmark`。CSV 的 `eval_count` 是 Solver 累计求值行数，包含两个子算法；`throughput_eval_s=eval_count/elapsed_s` 是自运行初始化以来的平均吞吐，绝非当前代瞬时速度。`step` 是回调的 generation 标签，不用它推断 CSV 行数或物理尝试数。`phase` 与 `pareto_archive_size` 在本宿主可以为空：没有启用对应发布者。

`best_score` 优先读 Solver context 的 best objective，再读 Solver 的 `best_objective`，之后才尝试 Adapter projection 和当前目标回退。因此是观察列，不能泛称每个算法都采用同一种比较。本例无 Bias、单目标，通常对应 Solver 的正式 incumbent 平方和；它不等于 wide/narrow 各自最终成员的完整列表。summary 的 `eval_count/elapsed_s/steps/status` 也是 finishing 时观察值，`status` 不证明后续 teardown/发布成功。本章覆写同名文件；先核对本次 Project 终态，不用旧 CSV 证明新运行。

**运行入口：** 从仓库根目录运行已有 Project 的 default 分组，随后读取本节指定的 CSV 与 summary。

```powershell
python examples/cases/catalog_recipes/run_project.py --group default
```

### 变体一：每次运行单独归档，拒绝同名覆盖

**目的：** 多次运行后按正式运行身份找回一对 CSV/summary，避免人工固定标签让后一次覆盖前一次。

**改在哪里：** 完整替换 `benchmark_recipe.py`；builder 仍调用同名工厂。读取时传实际运行 ID，而非默认 `composite` 标签。

```python
import csv
import json
from pathlib import Path
from nsgablack.plugins import BenchmarkHarnessConfig, BenchmarkHarnessPlugin


class CaseRunBenchmark(BenchmarkHarnessPlugin):
    def on_solver_init(self, solver):
        self.cfg.run_id = str(solver.run_session.run_id)
        return super().on_solver_init(solver)


def attach_benchmark(solver, output):
    plugin = CaseRunBenchmark(config=BenchmarkHarnessConfig(
        output_dir=str(output), seed=None,
        log_every=1, flush_every=1, overwrite=False,
    ))
    solver.add_plugin(plugin)
    return plugin


def read_benchmark(output, run_id):
    output = Path(output)
    with (output / f"{run_id}.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    summary = json.loads((output / f"{run_id}.summary.json").read_text(encoding="utf-8"))
    return {"rows": rows, "summary": summary}
```

**行为变化：** 运行初始化时 RunSession 已有身份，插件将该身份用于文件名；新运行产生另一对文件。拿两个明确 ID 调用 `read_benchmark`，先比较总求值量、终止状态和组件配置，再比较相同预算范围的墙钟。

**限制：** 这不会自动控制随机种子、硬件或并发，也不是恢复协议。恢复同一运行身份遇到已有 CSV，`overwrite=False` 会拒绝；应为恢复实验有意识地选择其它目录或覆盖策略，不能悄悄删旧文件继续。插件只检查 CSV 是否存在，不承诺保护一份孤立存在的同名 summary。

来源：[真实配置、提交行与分数读取顺序](../../plugins/ops/benchmark_harness.py)、[正式 builder](../../examples/cases/catalog_recipes/cases/composite/build_solver.py)、[Problem 与 starter](../../project/starter.py)。配套 key：`plugin.profiler`、`plugin.module_report`、`plugin.runtime_surface_tracker`。

## plugin.sequence_graph · 聚合同类调用顺序，再按需保留时间片

**什么时候用：** 排查根 Adapter 提案、Solver 送评和更新之间走了哪些调用路径，希望把重复顺序聚合成少量记录。图里的事件是调用观察，不是候选数据、因果证明或可执行回放。

**先准备什么：** 独立使用完整 `catalog_recipes/cases/composite` Case：二维单目标、wide/narrow 各四成员、两个逻辑步。根是 CompositeAdapter；自动包装根的 `propose/update`，不会递归给两个 NSGA2 每个内部方法插桩。本例显式按根 `propose` 划分周期，关闭插件事件和时间 trace，先观察结构顺序。输入不需要 Unit、候选或共享 context 自定义键。

**放在哪：** 新建 `cases/composite/plugins/sequence_recipe.py`，完整替换该 Case 的 builder。输出目录由 builder 传入，不依赖当前 shell 目录。

**接入步骤：** `plugins/sequence_recipe.py`：

```python
import json
from pathlib import Path
from nsgablack.plugins import SequenceGraphConfig, SequenceGraphPlugin


def attach_sequence(solver, output):
    plugin = SequenceGraphPlugin(config=SequenceGraphConfig(
        output_dir=str(output), run_id="composite", overwrite=True,
        flush_every=1, boundary_groups=[["adapter.*.propose"]],
        capture_adapter=True, capture_evaluate_population=True,
        capture_evaluate_individual=False, capture_plugin_events=False,
        trace_mode="off", max_sequence_length=1024, max_sequences=100,
    ))
    solver.add_plugin(plugin)
    return plugin


def read_sequences(path):
    graph = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        "cycles": graph["cycle_count"],
        "unique": graph["unique_sequences"],
        "sequences": graph["sequence_records"],
        "counts": graph["event_counts"],
        "dropped": graph["dropped_sequences"],
        "trace_events": graph["trace_events"],
    }
```

`cases/composite/build_solver.py`：

```python
from pathlib import Path
from nsgablack.project.starter import build_starter_solver
from nsgablack.project import apply_solver_component_overrides
from nsgablack.adapters import CompositeAdapter, NSGA2Adapter
from nsgablack.representation import GaussianMutation
from .problem import build_problem
from .pipeline import build_pipeline
from .plugins.sequence_recipe import attach_sequence


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = build_starter_solver(problem=build_problem(), pipeline=build_pipeline(),
                                  resource_context=resource_context, max_steps=2)
    solver.set_adapter(CompositeAdapter(adapters=[
        NSGA2Adapter(name="wide", population_size=4, offspring_size=4,
                     mutator=GaussianMutation(sigma=0.4)),
        NSGA2Adapter(name="narrow", population_size=4, offspring_size=4,
                     mutator=GaussianMutation(sigma=0.05)),
    ]))
    output = Path(__file__).resolve().parents[2] / "results" / "sequence"
    attach_sequence(solver, output)
    apply_solver_component_overrides(solver, component_overrides)
    return solver
```

初始化安装调用包装器；包装器在调用之前记录 token，异常继续传播。周期边界是 recorder 的匹配规则，不是 Solver 的 generation 提交屏障。提交钩子按配置刷新当前已完成的序列，finishing 恢复方法包装并封存最后一个周期；中途文件可能尚不含当前未封存周期。

**怎样判断接对：** 读取 Project 的 `results/sequence/composite.sequence_graph.json`，或把完整路径传给 `read_sequences`。核对 `schema_name="sequence_graph"`、`boundary_groups` 与本配置一致，`event_counts` 中能找到 `adapter.<根名称>.propose/update` 及 `solver.<类名>.evaluate_population`；不要期待自动出现 wide/narrow 叶方法。

`sequence_records` 各行有 `signature/count/length/events/truncated`，相同序列累计 count；`unique_sequences` 不是运行次数，`cycle_count` 不是提交数，`dropped_sequences>0` 表示达到唯一序列上限。`events` 达长度上限后会截断，核对 `truncated`。本配置 `trace_mode="off"`，时间 trace 应为空。`final=True` 只表示 finishing flush；result 中 `artifacts.sequence_graph_json` 是同一路径提示，不是成功收据。包装、token聚合和每次 flush 都有开销，记录不会替代实际算法日志或 checkpoint。

**运行入口：** 从仓库根目录运行已有 Project 的 default 分组，随后读取本节指定的 sequence_graph JSON。

```powershell
python examples/cases/catalog_recipes/run_project.py --group default
```

### 变体一：为一次短诊断开启完整时间 trace 和插件事件

**目的：** 需要看同一调用周期里插件通知与根调用的耗时、嵌套关系，而不止重复序列的计数。

**改在哪里：** 保留 `sequence_recipe.py` 的导入和读取函数，完整替换 `attach_sequence` 工厂；builder 不变。

```python
def attach_sequence(solver, output):
    plugin = SequenceGraphPlugin(config=SequenceGraphConfig(
        output_dir=str(output), run_id="composite", overwrite=True,
        flush_every=1, boundary_groups=[["adapter.*.propose"]],
        capture_adapter=True, capture_evaluate_population=True,
        capture_evaluate_individual=False, capture_plugin_events=True,
        trace_mode="full", trace_max_events=1000,
        max_sequence_length=1024, max_sequences=100,
    ))
    solver.add_plugin(plugin)
    return plugin
```

**行为变化：** 图增加插件事件 token，并保存 `trace_events`。方法包装产生 span，插件通知通常是 instant 事件；每行有 `token/start_ns/end_ns/duration_ns/thread_id/task_id/span_id/parent_span_id/status/error_type/trace_type`。可用 parent_span_id 对应父 span，按 duration_ns 排查耗时。`status="ok"` 是该调用/记录的状态，不等于整个优化运行成功。

**限制：** `trace_event_count` 是实际保留条数；超过1000条时 `trace_dropped_events` 增加，因此不能据此重建完整过程。`full` 比基线耗内存且 JSON 更大；不是分布式追踪，单调时钟纳秒也不是 UTC 时间。切回基线会覆盖同名文件，先保存诊断产物。

来源：[插件实际包装与 flush](../../plugins/ops/sequence_graph.py)、[周期、截断与 trace 字段](../../utils/runtime/sequence_graph.py)、[正式宿主](../../examples/cases/catalog_recipes/cases/composite/build_solver.py)。配套 key：`plugin.decision_trace`、`plugin.profiler`。

## plugin.runtime_surface_tracker · 用数据库查本次装配与运行观察记录

**什么时候用：** 希望运行后按 run_id、surface_key 或 assembly_signature 找回装配、指标摘要和产物路径，供本地工具消费。这里写的是正式运行面格式，持久化发生在 `on_solver_finish`，并不自动构成最终权威成功发布。

**先准备什么：** 独立使用现有 `catalog_recipes/cases/composite`，保留原 Problem/Pipeline 与 wide/narrow 两个算法。本章显式选 Project 内 SQLite 文件，不读取账号配置、不连接外部数据库。`case_root` 是包含 `build_solver.py` 的 Case 目录；配置名虽叫 project_root，传这里才能让当前实现定位到此装配入口。`surface_key` 是本应用稳定查询标签，run_id 由实际结果/运行身份解析，不能把标签当 run_id。

**放在哪：** 新建 Case 的 `plugins/surface_recipe.py`，完整替换 builder；同时新增 `plugins/read_surface.py` 作为运行后读取入口。读取器不调用 Solver，也不创建算法 Unit。

**接入步骤：** `plugins/surface_recipe.py`：

```python
from pathlib import Path
from nsgablack.plugins import RuntimeSurfaceTrackerConfig, RuntimeSurfaceTrackerPlugin


def attach_surface(solver, output, case_root):
    output = Path(output).resolve()
    plugin = RuntimeSurfaceTrackerPlugin(config=RuntimeSurfaceTrackerConfig(
        db_path=str(output / "surface.sqlite3"),
        namespace="catalog_recipes", tag="composite_observation",
        project_root=str(case_root), surface_key="solver:catalog_recipes.composite",
        surface_label="Composite observation", print_summary=False,
    ), priority=100)
    solver.add_plugin(plugin)
    return plugin
```

`cases/composite/build_solver.py`：

```python
from pathlib import Path
from nsgablack.project.starter import build_starter_solver
from nsgablack.project import apply_solver_component_overrides
from nsgablack.adapters import CompositeAdapter, NSGA2Adapter
from nsgablack.representation import GaussianMutation
from .problem import build_problem
from .pipeline import build_pipeline
from .plugins.surface_recipe import attach_surface


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = build_starter_solver(problem=build_problem(), pipeline=build_pipeline(),
                                  resource_context=resource_context, max_steps=2)
    solver.set_adapter(CompositeAdapter(adapters=[
        NSGA2Adapter(name="wide", population_size=4, offspring_size=4,
                     mutator=GaussianMutation(sigma=0.4)),
        NSGA2Adapter(name="narrow", population_size=4, offspring_size=4,
                     mutator=GaussianMutation(sigma=0.05)),
    ]))
    case_root = Path(__file__).resolve().parent
    output = case_root.parents[1] / "results" / "surface"
    attach_surface(solver, output, case_root)
    apply_solver_component_overrides(solver, component_overrides)
    return solver
```

运行后用 `plugins/read_surface.py` 读取真实公开查询 API 的返回值；先验证文件存在，避免把路径写错后查询一个新空库。

```python
import argparse
import json
from pathlib import Path
from nsgablack.plugins import list_runtime_run_surfaces


def read_surface(db_path):
    path = Path(db_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    rows = list_runtime_run_surfaces(
        path, surface_key="solver:catalog_recipes.composite", limit=20)
    return [{
        "run_id": row["run_id"], "status": row["status"],
        "assembly_signature": row["assembly_signature"],
        "entry_path": row["surface_record_json"]["entry_path"],
        "slots": row["assembly_record_json"]["component_slots_json"],
        "metrics": row["run_record_json"]["metric_summary_json"],
        "artifacts": row["artifact_records_json"],
    } for row in rows]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("db_path")
    args = parser.parse_args()
    print(json.dumps(read_surface(args.db_path), ensure_ascii=False, indent=2))
```

**怎样判断接对：** 默认 DB 是 Project 的 `results/surface/surface.sqlite3`。读取结果的 `entry_path` 应指向本 Case 的 build_solver.py；`slots.adapter` 描述根 CompositeAdapter，`slots.operator_bindings` 可核对按所有者路径记录的两个 GaussianMutation 绑定。`metrics` 包含 finishing 时的 `best_objective/steps/generation/evaluation_count`，不是完整候选种群；两个子种群仍通过各自 partition 保持身份，不会被该插件合并。

原 Solver result 还含 `run_surface.surface_record/assembly_record/run_record/artifact_records/db_path`，以及 `artifacts.runtime_surface_db/runtime_surface_run_ref`；标准终端摘要不保证展示整包，用上述数据库读取器消费。SQLite 的一条 run_id 通过 upsert 更新，同一身份重写不是追加一次新实验。`status` 来自 finishing result，后续 teardown 仍可能失败，需和标准 Case 最终状态对账。此插件收集静态描述并写数据库，有 SQL/序列化开销；本例没有申请评估决定或最终发布否决权限。

**运行入口：** 两条命令按顺序手动执行：先运行正式 Project，再读它写出的本地数据库。

```powershell
python examples/cases/catalog_recipes/run_project.py --group default
python examples/cases/catalog_recipes/cases/composite/plugins/read_surface.py examples/cases/catalog_recipes/results/surface/surface.sqlite3
```

### 变体一：把 benchmark 文件索引与运行面记录接起来

**目的：** 查询运行面时同时找到 CSV/summary 路径，不再只得到数据库自己的两个 artifact 提示。

**改在哪里：** 完整替换 `surface_recipe.py` 为以下内容；本章 builder、读取器与命令均不变。每次采用本变体时不要另挂同名 benchmark 插件。

```python
from pathlib import Path
from nsgablack.plugins import (
    BenchmarkHarnessConfig, BenchmarkHarnessPlugin,
    RuntimeSurfaceTrackerConfig, RuntimeSurfaceTrackerPlugin,
)


def attach_surface(solver, output, case_root):
    output = Path(output).resolve()
    solver.add_plugin(BenchmarkHarnessPlugin(config=BenchmarkHarnessConfig(
        output_dir=str(output / "benchmark"), run_id="composite",
        seed=None, log_every=1, flush_every=1, overwrite=True,
    ), priority=0))
    tracker = RuntimeSurfaceTrackerPlugin(config=RuntimeSurfaceTrackerConfig(
        db_path=str(output / "surface.sqlite3"),
        namespace="catalog_recipes", tag="composite_with_benchmark",
        project_root=str(case_root), surface_key="solver:catalog_recipes.composite",
        surface_label="Composite observation", print_summary=False,
    ), priority=100)
    solver.add_plugin(tracker)
    return tracker
```

**行为变化：** PluginManager 按 priority 从小到大通知，benchmark 的 finishing 先把 `benchmark_csv/benchmark_summary_json` 加入 artifacts，tracker 随后持久化这些路径。读取器返回的 `artifacts` 列表可找到相同 artifact_id；实际文件位于 `results/surface/benchmark/composite.csv` 和 `.summary.json`。`slots.plugins` 也增加 benchmark 的引用。

**限制：** 这是路径索引，不会把文件内容装入数据库，也不自动验证文件摘要或授予读取权限。相对路径不会搬迁成可移植包；本例传的是绝对输出路径。同名文件后续覆盖会影响旧路径所指内容，因此多次实验需要独立输出目录。指标与文件仍在 finishing 阶段，不能因数据库有一行就认定最终发布成功。

来源：[记录构造、写入与查询](../../plugins/storage/runtime_surface_tracker.py)、[显式 SQLite 目标优先级](../../experiment/db.py)、[正式 Case](../../examples/cases/catalog_recipes/cases/composite/build_solver.py)、[共享 Plugin 优先级](../../../blackbase/src/blackbase/plugin/base.py)。配套 key：`plugin.benchmark_harness`、`plugin.module_report`。
