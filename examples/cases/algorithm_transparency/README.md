# 算法透明性验收 Project

本 Project 比较同一算法的独立裸内核与完整 `ComposableSolver.run()` 路径，回答：候选身份、Pool、Unit、事务和证据是否改变算法结果，以及为它们付出多少额外时间。

## 安装与入口

在仓库根目录安装测试依赖；pymoo 是可选 benchmark 依赖，不加入普通用户依赖：

```powershell
python -m pip install -e ".[benchmark,dev]"
python examples/cases/algorithm_transparency/run_project.py --check --build-check
python examples/cases/algorithm_transparency/run_project.py --group default
```

若使用本次创建的隔离解释器，将 `python` 替换为 `.benchmark-venv\Scripts\python.exe`。

所有正式运行走标准 Project → Case → scaffold。`project_config.py` 管阶段、并行与资源；`cases/*/build_solver.py` 是薄入口；`benchmarks/transparency_case.py` 实现共享验收 Case；`benchmarks/transparency_core.py` 调用真实 Solver 生命周期。裸参考是独立数值循环，不创建 Adapter/Unit/Solver/Pool。

也可独立运行某个 Case。薄 CLI 委托同一 Project runner 建立 CaseRuntime，继续使用正式授权与发布：

```powershell
python examples/cases/algorithm_transparency/cases/bare_inner/run_solver.py --check
python examples/cases/algorithm_transparency/cases/nested_outer/run_solver.py
```

## 运行组

- `default`：小型矩阵、两个真实并行 Case 和跨 Case 嵌套，适合首次检查装配。
- `full`：registry 所有配对，每对使用种子 11、29，核对完整运行与真实 checkpoint 前缀恢复。
- `quality`：六个多目标配对，种群 30、25 次提交、种子 11/29/47。每对两条路径均为 750 次实际 Problem 调用，初始化计入。此组不重复恢复验收。
- `classical`：NSGA-II、NSGA-III、MOEA/D 与独立 pymoo 整算法进行效果对照，默认种群 20、实际评估 400、两个 seed。共同算子、方向、预算及仍有差异的抽样/平局方式记录在报告中；不是默认 SBX/PM 配方或文献最佳值认证。
- `parallel`：Project 发起两个独立 Case 进程，报告保存 PID、起止时间、L0 绑定和 Artifact 收据；Adapter multi 合并提案不冒称多进程并行。
- `nested`：正式 `CaseRuntime.invoke(CaseRunRequest(...))` 调用内层 Case 的 matrix 模式，比较相同输入的直接裸参考与内层真实 Solver.run 交付状态、轨迹、实际求值序列和计数。内层有独立运行身份、授权和 Artifact；单独 bare_inner 裸阶段只是附加对照。

```powershell
python examples/cases/algorithm_transparency/run_project.py --group full
python examples/cases/algorithm_transparency/run_project.py --group quality
```

quality 的六个配对：NSGA-II/ZDT1、NSGA-III/ZDT1、NSGA-III/DTLZ2、SPEA2/ZDT1、MOEA/D/ZDT1、DE/ZDT1。

## 调整规模

在 project_config.py 的 matrix `component_overrides.config` 中显式指定：

```python
{
    "names": ["nsga2_zdt1", "nsga3_dtlz2"],
    "population_size": 100,
    "steps": 100,
    "seeds": [11, 29, 47],
    "recovery": True,
}
```

population_size/steps 只调整人口算法。A* 有限图、轨迹算法和组合任务各用自己的步数，不用一个全局代数强改它们。先测吞吐再增加规模；小预算通过不能替代大维度、多约束、多种子的收敛统计。

## 指标来源

HV/IGD 直接调用 `pymoo.indicators.hv.HV` 和 `pymoo.indicators.igd.IGD`。非支配筛选也调用 pymoo，没有自写备用指标。

`benchmarks/reference_sets/` 保存固定参考前沿文件。manifest 记录官方生成器、pymoo 版本、参数、生成器源码摘要、文件 SHA-256、形状及固定 HV 参考点。ZDT1 是官方生成器的 1000 点；DTLZ2 是官方 Das-Dennis 三目标 32 分割的 561 点。它们由官方 Problem.pareto_front 生成，不伪称从 pymoo-data 下载了不存在的同名文件。

测量只读并校验文件，不联网取数，不按本次结果改变参考点。HV 参考点固定为 ZDT1 `[1.1, 11]`、DTLZ2 `[3, 3, 3]`，按 fixture 目标范围事先选定；不能直接与采用其他参考点的论文数字比较。仅测最终可行非支配成员，不把历史所有评估点当最终输出。无可行成员时 HV=0、IGD 明确未定义。

如需更新版本或点数，先同步依赖与准备脚本，再显式生成：

```powershell
python -m benchmarks.prepare_transparency_references
```

这是参考数据准备工具，不是另一个私有求解入口。

## 报告含义

`.blackbase/artifacts/` 保存正式 JSON Artifact；执行记录保留运行身份与状态；Case `results/` 保存前缀 checkpoint。每对独立报告：

- `semantics`：逐提交状态、最终状态、实际 Problem 调用顺序和次数、逻辑步数；差异给出具体字段路径。
- `quality`：人口配对的官方 HV/IGD、差值、最终种群大小和参考来源；其他算法保留自身状态/原始反馈，不硬套 HV。
- `overhead`：墙钟、CPU、Problem 自身耗时、RSS 观测与 I/O；measured 表示已测，不表示性能达标。人口组另分初始化和正常迭代。
- `recovery`：真实 committed-prefix checkpoint → 新建 Solver → 正式 resume，核对后缀轨迹、最终状态与求值序列，恢复不能偷偷再评估。

计时包含生命周期、事务、证据和语义 trace；装配单列，官方指标在求解计时之外。RSS 是进程边界/提交点观测最大值；同一进程保留参考轨迹供语义对照，因此它也不是两条路径各自隔离的内存基准。默认内存运行后端的数字不能代表所有存储后端；并行组不用于推导串行算法成本。

每个内部 Solver 的高频控制检查委托同一父 CaseRuntime.checkpoint，复用父级控制 owner、心跳与缓存，前缀/恢复运行也接入。Solver 证据保留于本地存储，只有聚合报告经外层 Case 正式发布，不将多次内部 Solver finalization 冒充独立 Case Artifact 发布。

## 故障与取消

故障测试另用真实 SQLite L0 预算、文件 Snapshot 和证据日志，不计入性能。首步提交后，在下一次真实 update 后注入失败或取消，要求：算法/权威/公开池退回上一提交；实际求值和消耗预算保留；重开持久组件后证据仍一致；故障 checkpoint 恢复不新增 Problem 调用和预算。

BO 可以学习真实发生的失败尝试观测，故不强求失败后继续的搜索轨迹等于从未失败。测试核对证据与计账，不抹掉算法知识。

```powershell
python -m pytest tests/test_transparency_population.py tests/test_transparency_trajectory.py tests/test_transparency_structured.py tests/test_transparency_composition.py tests/test_transparency_protocols.py tests/test_transparency_metrics.py tests/test_transparency_core_meter.py tests/test_transparency_faults.py
```

全 registry 的双故障矩阵约需五分钟，显式开启：

```powershell
$env:NSGABLACK_FULL_TRANSPARENCY_FAULTS = "1"
python -m pytest tests/test_transparency_fault_matrix.py -q
Remove-Item Env:NSGABLACK_FULL_TRANSPARENCY_FAULTS
```

默认跳过这个昂贵矩阵；跳过不计入通过数。普通恢复由 full 组单独实际执行。

公开覆盖登记见 `benchmarks/transparency_registry.py`；无执行报告只能 registered，新增未配对具体 Adapter 显示 uncovered；抽象基类永不计为算法通过。变体和局限写在各 PairSpec.metadata。详细实验边界见 `docs/architecture/ALGORITHM_TRANSPARENCY_BENCHMARK_CN.md`。

## Doctor 的当前限制

本 Project 的正式 build-check 已通过。严格 Doctor 当前为 0 error、10 warning（退出码 1）：五个验收包装 Case 的实际 pipeline 工厂由 PairSpec 持有，没有独立 Case pipeline/main.py；包装层也没有共享 context 键契约，因此各有一条推荐/空契约警告。报告保存在 `results/doctor_build.json`。这不是严格 Doctor 全绿；它也不能代替上述行为验收。Case catalog 未登记 TOML 的跳过信息另行保留，不伪造未发生的 catalog 审核。

## 不同评估成本与 trace 的分离实验

```powershell
python examples/cases/algorithm_transparency/run_project.py --group costs
```

该组用相同 NSGA-II、种群 8、8 次提交、seed 11/29，分别测试固定 NumPy CPU 工作量（目标 0/1/10/50 ms）、模拟 I/O 等待 10 ms，以及原 production_scheduling 的 22×31 变量 Problem 和供料 repair。CPU 工作量在求解计时之外用长采样校准，避免 Windows 粗 CPU 时钟读零；每次执行固定工作次数，输出目标值不变。以实际 Problem 耗时为准，不拿标称值代替结果。

每个 fixture 先通过完整语义与 checkpoint 验收，然后轮换次序运行三种观察模式：full（逐提交状态/RSS和逐次求值记录）、no_step_trace（仅逐次调用记录）、lean（两种记录均关闭）。三种模式都保留正式身份、Pool、Unit、事务、证据、预算和父 Case 控制。最小阶段计时/计数仍保留；lean 不是无测量开销的理论极限。

只统计 bootstrap 之后的七次正常提交，分别列出 Problem、repair、剩余时间；剩余时间包含算法本身及运行时，不能全部归因于框架。完整/无逐步记录/lean 的带符号差值估计 trace 开销，差值保留负数，不把时序噪声裁成零；另列扣除实测评估/repair 波动后的差值，以及逐步回调自身计时。两个种子是诊断样本，不是统计置信区间。

原排程模型和原始 CSV/XLSX 数据经原 Case 正式工厂加载，明确拒绝合成 fallback；不移动任何到料或今天库存。此组使用匹配的 NSGA-II 对照，不声称运行了原多算法编排或完整外层供应调整。指标无已知真实 Pareto 参考集，因此比较原目标/约束与算法轨迹，不伪造排程 HV/IGD。

通过后，报告为标准 Case 的正式 report Artifact；逐 fixture 的进度/资格验收另存于 Case results。离线导出用 `benchmarks.transparency_cost_report.export(manifest_path, destination)`，只读取已经发布的校验报告，不启动新求解。
# 修改任务对照入口

执行 `python run_project.py --group modifications --run-id <唯一运行ID>`，通过正式 matrix Case
比较 nsgablack 与 pymoo 0.6.2 的成员年龄、年龄选择和精修器换装。
范围、实际结果与公平性限制见 [修改任务对照](../../../docs/architecture/MODIFICATION_TASK_COMPARISON_CN.md)。
本组不是优化质量排行榜，学习成本未经过用户实验测量。
