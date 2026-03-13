# NSGABlack 工程技术栈（实现说明版）

本文件不再做“承诺对齐检查”，而是把当前仓库里已经落地的工程能力按模块拆开说明：实现在哪里、关键机制是什么、输出/副作用是什么、边界在哪里。

## 0. 能力地图（从“我要什么”到“我该看哪”）

| 你要的能力 | 推荐入口/组件 | 关键实现文件 | 产物/输出 |
| --- | --- | --- | --- |
| 组装一个可运行的实验（问题 + 算法 + 口径 + 输出） | `utils/wiring` 的 `attach_*` + `plugin.*` | `utils/wiring/`、`plugins/` | 运行目录下 CSV/JSON/报告文件 |
| 统一实验口径（逐步记录 + summary） | `plugin.benchmark_harness` | `plugins/ops/benchmark_harness.py` | `steps.csv`、`summary.json` |
| 模块/偏置生效审计（“到底是谁在起作用”） | `plugin.module_report` | `plugins/ops/module_report.py`、`plugins/base.py` | `modules.json`、`bias.json`（可选 `bias.md`） |
| 并行评估（加速 evaluate + bias/constraint） | `with_parallel_evaluation(...)` | `utils/parallel/evaluator.py`、`utils/parallel/integration.py` | 进程/线程池并行评估结果 |
| 约束计算与容错 | `evaluate_constraints_safe(...)` | `utils/constraints/constraint_utils.py` | 约束向量 + violation |
| Context 约定（跨模块共享信息） | `context_keys.*` | `utils/context/context_keys.py` | 统一 key 命名与约定 |
| Catalog（“官方推荐入口”索引） | `python -m nsgablack catalog ...` | `catalog/registry.py` | CLI 列表/详情 |

说明：
- 本项目的“主路径”是 `wiring + plugin`，`core/solver.py` 作为稳定底座尽量不作为文档主入口。
- Windows 下运行 CLI 时，建议从仓库根目录（`nsgablack/` 的父目录）执行；如果当前目录就是 `nsgablack/`，`python -m nsgablack` 会因为模块搜索路径而找不到同名包。

## 1. 代码结构与边界（我应该把东西放哪）

### 1.1 Core：稳定底座（尽量不装配）

定位：通用求解生命周期与基础接口，追求“稳定、可复用、少副作用”。

- 求解器底座与通用接口：`core/`
- “不要在 core 里做装配”：装配放到 `utils/wiring/`，生态能力放到 `plugins/`

### 1.2 Representation：表示与变换管线（可插拔）

定位：把“个体怎么表示/怎么变换/怎么修复”从 solver 中拿出来，避免算法与业务耦合。

- 表征相关实现：`representation/`
- 典型形态：encode/decode/repair/clip/normalize 等步骤以 pipeline 组合（具体以 `representation/` 内模块为准）

### 1.3 Bias：偏置与惩罚（以组合为主，不以继承为主）

定位：把“你认为更好/更合理”的判断显式化，变成可审计、可开关、可调参的模块。

- 偏置组合器：`bias/bias_module.py`
- 组合方式：`bias.add(CallableBias(...))`（旧的 `add_penalty` 已移除，避免 API 隐式膨胀）
- 输出/审计：见 `plugins/ops/module_report.py` 对 bias 的导出

### 1.4 Plugin：生态能力（调度/记录/导出/增强）

定位：把“非核心生命周期但很必要的工程能力”做成插件，避免 solver 文件继续膨胀。

- 插件基类与 manager：`plugins/base.py`
- 典型插件：
  - 实验口径：`plugins/ops/benchmark_harness.py`
  - 模块/偏置报告：`plugins/ops/module_report.py`
- 工程机制：
  - 插件可声明 `is_algorithmic`（用于“贡献报告”筛选：哪些算算法模块，哪些是胶水模块）
  - PluginManager 对插件 hook 进行计时/采样（实现以 `plugins/base.py` 为准）

### 1.5 Wiring：装配层（官方推荐入口）

定位：把“用哪些 solver/adapter/插件/默认参数”统一收敛在 wiring；core 不做装配，wiring 做。

- wiring 目录：`utils/wiring/`
- catalog 伙伴组件：`catalog/registry.py` 中的 `companions`/推荐条目会把 wiring 与关键插件绑成“权威路径”

## 2. 组件通信与数据流（没有事件总线，但有统一上下文）

### 2.1 通信方式：函数调用 + Context Dict

本框架没有引入独立事件总线/消息队列；核心通信是“明确的函数调用链”，并用 `context: dict` 传递跨模块信息。

- Context 约定：`utils/context/context_keys.py`
- 最小 context 构造：`utils/context/context_schema.py`（并行评估会用它构造可序列化的最小 context）
- 常见数据：
  - `generation`、`individual_id`
  - `constraints`、`constraint_violation`
  - `seed`、`metadata`
  - `problem` 引用（为兼容需要访问问题信息的 bias/repair）

### 2.2 为什么不用“统一 Context 类/DI 容器”

工程取舍（当前实现）：
- Context 用 dict：低侵入、易扩展、跨进程传递时更容易裁剪成“可序列化最小集合”
- DI 不引入容器：装配放在 wiring，靠显式构造注入；避免生命周期系统带来的复杂度

## 3. 并行与性能（并行的是评估，不是“框架本身”）

### 3.1 并行评估的落点

目标：加速最慢的环节（通常是 `problem.evaluate(x)` + 约束 + bias），而不是让 solver 结构更复杂。

- 并行评估器：`utils/parallel/evaluator.py`
  - 后端：`ProcessPoolExecutor` / `ThreadPoolExecutor`（`concurrent.futures`）
  - Windows spawn 成本：首次创建进程池会慢（进程启动 + 依赖导入 + 预热），之后趋于稳定
  - 可 picklable 检测：对跨进程对象做序列化可行性检查（避免“跑到一半才炸”）
  - factory 模式：支持 `problem_factory()` 在子进程内构造 problem（避免直接跨进程传 problem 实例）
- 一键集成 wrapper：`utils/parallel/integration.py` 的 `with_parallel_evaluation(...)`

### 3.2 线程后端 vs 进程后端（工程上怎么选）

- `thread`：
  - 优点：启动快、共享内存、对象无需 pickling、在 I/O 重/释放 GIL 的算子（numpy/scipy）可能收益明显
  - 缺点：纯 Python CPU 密集会被 GIL 限制；线程间共享状态更容易踩数据竞争
- `process`：
  - 优点：绕过 GIL、CPU 密集更稳；隔离更强（不共享内存，避免部分隐式副作用）
  - 缺点：启动慢（Windows 更明显）、需要 picklable、传参/回传有序列化成本

### 3.3 是否使用 asyncio / 异步 IO

当前实现不依赖 `asyncio`：
- 主要瓶颈是 CPU 密集的评估/修复/偏置计算，用协程收益不大
- 输出（CSV/JSON/Excel）是低频落盘，采用同步 IO 更简单、故障模式更少

如果未来要做“在线服务化/远程评估/分布式执行”，再考虑把评估层升级为异步/远程调用；那会是并行模块的扩展，而不是 core 的改造。

## 4. 可复现与可审计（实验口径与模块贡献）

### 4.1 统一实验口径：BenchmarkHarnessPlugin

- 插件：`plugins/ops/benchmark_harness.py`
- 关键输出：
  - 每步/每代的逐步记录（CSV）
  - run 级 summary（JSON）：seed/time/eval_count/best_score 等
- 工程点：
  - “口径与算法逻辑分离”：算法只管产生候选与评估，口径插件只管记录与导出

### 4.2 模块贡献报告：ModuleReportPlugin

- 插件：`plugins/ops/module_report.py`
- 关键输出：
  - `modules.json`：启用的插件/adapter/bias/pipeline 组件清单与元信息
  - `bias.json`：bias 细项的累计/统计（以 bias 能提供的信息为准）
  - 可选 `bias.md`：把偏置拆解成可读报告（用于展示/审计）
- 工程点：
  - 插件计时：基于 PluginManager hook profiling（见 `plugins/base.py`）
  - “算法模块”识别：插件可标记 `is_algorithmic`，报告按此过滤/聚合

## 5. 配置、加载与兼容（让用户更容易“跑起来”）

### 5.1 配置/实验组织（工程侧落点）

- 实验组织/落盘工具：`utils/engineering/experiment.py`
- 目标：把“运行参数、输出目录、复现实验信息”从脚本里抽出来（即便你不写论文复现，也需要可追溯）

### 5.2 兼容层（仅做过渡，不做长期依赖）

- 兼容工具/旧路径适配：`utils/compat/solver_extensions.py`
- 建议：新代码只依赖 `wiring + plugin` 主路径；compat 只服务于历史脚本迁移

## 6. Catalog：索引是显式注册（可控、可审计）

- 注册表：`catalog/registry.py`
- 机制：显式 key -> 组件对象（或工厂），并维护 companions（伙伴组件）
- 取舍：
  - 优点：稳定、可控、避免“扫描导入”引入副作用（尤其是插件/solver import 时）
  - 缺点：新增条目需要改 registry（当前的“显式可控”换来的成本）

如果要做“自动装配”，比较安全的方向是：
- 仅扫描“无副作用的元数据”（例如通过 entry_points 或静态声明文件），并延迟导入（lazy import）
- 保持 registry 作为“官方推荐清单”，自动发现只做“候选收集”，不要取代推荐路径

## 7. 包管理、导入路径与可选依赖（让用户少踩坑）

### 7.1 包管理与安装方式

- 构建/依赖声明：`pyproject.toml`
- 推荐开发安装（可编辑）：`python -m pip install -e .`
- 常见坑（Windows / PowerShell）：
  - `python -m nsgablack ...` 必须在“仓库根目录的父目录”执行（也就是包含 `nsgablack/` 这个包目录的那一层）
  - 如果当前工作目录就是 `nsgablack/`，Python 会把当前目录当作 sys.path[0]，导致 `import nsgablack` 解析路径异常（表现为 `No module named nsgablack`）

### 7.2 可选依赖与“安全导入”

本项目在工程上倾向于“核心不强依赖可选能力”，因此对可选依赖采用了显式的安全导入封装：

- 统一导入工具：`utils/runtime/imports.py`
  - `safe_import(module, attr=None, fallback=None)`：依赖缺失不直接崩溃（可选择 warn）
  - 可选特性分组检查：`check_optional_dependency(feature)`
  - 典型特性分组：`visualization` / `parallel` / `machine_learning` / `acceleration`

工程取舍：
- 优点：用户环境不完整时也能跑核心能力；文档可以把“增强能力”标成可选
- 缺点：如果滥用 fallback，可能把“真实错误”掩盖成“返回 None”；因此建议只对“可选增强”使用 safe_import，对核心路径保持硬失败

## 8. 日志、指标与运行产物（工程可观测性）

### 8.1 日志：结构化 JSON / 文本两种输出

- 日志配置：`utils/engineering/logging_config.py`
  - `configure_logging(level=..., json_format=..., log_file=...)`
  - JSON formatter 适合后续脚本解析/汇总（尤其是批量实验）

说明：日志与“实验口径产物”是两条线：
- 日志用于“运行时调试/排障”
- 口径产物（CSV/JSON）用于“对齐实验、做统计、写报告”

### 8.2 实验口径产物：CSV/JSON（可追溯、可对比、易汇总）

- BenchmarkHarness：`plugins/ops/benchmark_harness.py`
  - `steps.csv`：逐步/逐代记录（可用于画收敛曲线、做 time-to-target）
  - `summary.json`：run 元数据（seed/time/eval_count/best_score 等）
- ModuleReport：`plugins/ops/module_report.py`
  - `modules.json`：本次 run 启用的“算法模块 + 胶水模块”清单
  - `bias.json`：偏置/惩罚的累计贡献信息（以 BiasModule 暴露的信息为准）

### 8.3 为什么不做“强约束的 Metrics SDK”

当前版本没有引入 Prometheus/OTel 这类重型指标系统，原因是：
- 主场景是离线实验/本地批跑，不是在线服务
- 成本更低的 CSV/JSON 已覆盖“对齐口径 + 可追溯”的目标

如果未来需要“持续跑服务化/集群化”，可以在 plugin 层引入指标后端，而不是在 core 里硬编码。

## 9. 配置与实验组织（把工程细节从脚本里挪走）

### 9.1 配置加载：JSON/TOML/YAML（工程上可落地）

- 配置加载/合并/校验：`utils/engineering/config_loader.py`
  - `load_config()`：支持 `.json/.toml/.yaml`
  - `merge_dicts()`：深合并（override wins）
  - `apply_config()`：把 config 映射到对象属性（支持 unknown keys 检测）
  - `build_dataclass_config()`：面向 dataclass 的配置注入（可 strict）

工程建议：
- wiring 作为“权威装配层”，可以提供默认 dataclass config；用户通过外部 config 覆盖
- 对外 demo 尽量用“配置 + wiring”驱动，避免脚本里散落一堆参数

### 9.2 实验结果结构化落盘（轻量版 experiment tracking）

- 实验结果容器：`utils/engineering/experiment.py`
  - `ExperimentResult.save()`：输出 `pareto.csv/config.json/history.json`
  - 对 numpy 类型做递归序列化，避免 JSON 写入失败

边界：
- 这是轻量“产物组织”，不是 MLflow/W&B 那种全功能平台；但足够支撑本地复现实验与报告生成

## 10. 兼容层与弃用策略（怎么“删旧 API”而不伤用户）

### 10.1 兼容层的放置与目标

- 兼容层位置：`utils/compat/`
- 目标：让历史脚本“还能跑/能迁移”，但不鼓励新代码继续依赖

### 10.2 弃用提示：warning 而不是悄悄兼容

典型做法：
- 保留一个薄 wrapper（re-export），在调用时 `warnings.warn(..., DeprecationWarning, stacklevel=2)`
- 文档与 catalog 的“权威路径”不再指向兼容层

示例（可参考）：
- `utils/runs/headless.py` 中对旧功能的 DeprecationWarning：明确告诉用户要迁移到 `RepresentationPipeline + plugins/wiring helpers`

## 11. 失败模式与健壮性（真实问题一定会炸，怎么炸得可控）

### 11.1 约束评估容错

- 约束工具：`utils/constraints/constraint_utils.py`
- 目标：把“约束格式多样/异常”统一收敛为：
  - `constraints` 数组（可能为空）
  - `violation`（单一可排序的违反程度）

### 11.2 并行评估的异常隔离

并行评估的关键原则：个体失败不应当拖死整轮实验。

在 `utils/parallel/evaluator.py` 中的策略是：
- 捕获 `evaluate/constraint/bias` 的异常
- 失败个体返回 `inf` 目标值与 `inf` violation（并携带错误字符串），确保算法可以继续推进

### 11.3 可选依赖缺失的行为约定

- 可选能力缺失：返回 fallback + warning（见 `utils/runtime/imports.py`）
- 核心能力缺失：应当硬失败（例如核心 solver/bias/representation 不应当被 silent fallback 掩盖）

## 12. 性能工程（框架不等于慢，慢的是评估与数据流）

### 12.1 性能主要落点

在黑箱优化中，最常见瓶颈是：
- `problem.evaluate(x)` 本身（昂贵仿真/业务计算）
- 约束与修复（repair/clip/feasibility）
- 偏置模块（尤其是复杂的 penalty/打分组合）

因此“框架层”最划算的性能优化是：
- 并行评估（见第 3 节）
- 尽量让表征/修复/偏置函数可向量化（numpy 批量计算），减少 Python 循环

### 12.2 内存与资源管理（避免长跑崩溃）

- 内存监控/管理：`utils/performance/memory_manager.py`
  - 典型用途：长时间批跑时做 periodic cleanup/统计（以实现为准）

### 12.3 可视化不是核心，但要“低侵入”

定位：可视化属于“可选增强”，不应当污染用户环境（例如 import 时强行切 backend）。

- 可视化适配：`utils/viz/`
- 推荐做法：通过 plugin 或 wiring helper 控制可视化启用，而不是在包 import 时做全局副作用设置

## 13. 扩展开发指南（给贡献者一个“按部就班的入口”）

### 13.1 新增一个插件（Plugin）

工程约束：
- 插件必须是“可独立插拔”的：没有它也能跑；有它只是增强
- 插件尽量只读 context/solver 状态，少改 solver 内部字段

入口与基类：
- `plugins/base.py`

建议最小模板（概念示例，具体 hook 名以基类为准）：
```python
from nsgablack.utils.plugins.base import Plugin

class MyPlugin(Plugin):
    name = "my_plugin"
    is_algorithmic = False

    def on_run_start(self, solver, context):
        ...

    def on_step_end(self, solver, context):
        ...
```

### 13.2 新增一个 Wiring（官方推荐装配）

工程约束：
- wiring 负责“装配”，不要把算法细节塞进 core
- wiring 输出要尽量可复用：给外部脚本一个稳定的“开箱即用”入口

入口：
- `utils/wiring/`

### 13.3 新增 catalog 条目（让用户能搜到）

当前机制是显式注册（可控、可审计）：
- `catalog/registry.py`

建议规则：
- `utils/wiring` 的 `attach_*` 始终优先作为“推荐入口”
- 原子组件（bias/representation/plugin）可以注册，但要写清楚 companions（把“怎么组装”绑定上）

## 14. Catalog 自动装配（如果你要做，建议怎么做）

你提到“每次都改 registry 太麻烦”，要自动装配，建议按风险分层：

### 14.1 低风险：自动发现 + 手工推荐清单并存

- 自动发现只做“候选列表”，不直接成为默认推荐
- `catalog/registry.py` 继续作为“官方推荐清单”（稳定、可控）

实现方式（推荐优先级从高到低）：
1) Python entry_points（安装时注册元数据，运行时读取；天然避免扫描导入）
2) 静态声明文件（例如 `catalog_entries.json`），运行时读取 import_path 字符串并 lazy import

### 14.2 中风险：扫描包结构（必须 lazy import）

如果用 `pkgutil.walk_packages` 扫描模块，需要注意：
- 扫描阶段不能 import 目标模块（否则会触发副作用、慢启动、依赖缺失直接炸）
- 正确做法是扫描“模块名字符串”，只在 `CatalogEntry.load()` 时 import

### 14.3 高风险：import 即注册（强副作用，不建议）

这种模式的问题是：
- 一旦模块 import 有副作用（注册、读文件、设置全局 backend），用户环境就会被污染
- optional dependency 缺失会导致 catalog 初始化都失败

结论：自动装配可以做，但要以“lazy + 元数据”为前提，不要用“import 就执行注册”的老路。

## 15. Plugin 生命周期与工程契约（hook 参考）

本节是“写插件时你必须对齐的契约”，用于避免插件彼此踩踏、避免把 solver 变成胶水堆。

### 15.1 标准 hook 列表（按触发顺序）

实现：`plugins/base.py`

Solver 初始化阶段：
- `on_solver_init(solver)`：插件 attach 完成后立刻调用；适合创建输出目录、初始化随机种子、打开文件句柄
- `on_initialization(solver)`：旧接口兼容（同义）；新插件优先实现 `on_solver_init`

种群阶段：
- `on_population_init(population, objectives, violations)`：初始种群完成后调用；适合做一次性统计/快照

迭代阶段：
- `on_generation_start(generation)`
- `on_generation_end(generation)`：BenchmarkHarness 在这里写一行 CSV（见 `plugins/ops/benchmark_harness.py`）

空白求解器/自定义循环阶段：
- `on_step(solver, generation)`：给 SolverBase 这类“外部循环”提供的每步回调

结束阶段：
- `on_solver_finish(result: dict)`：求解器结束时触发；适合写 summary/导出报告
- `on_completion(solver)`：旧接口兼容（同义）；新插件优先实现 `on_solver_finish`

### 15.2 调度顺序、优先级与短路（short-circuit）

实现：`plugins/base.py` 的 `PluginManager`

- 插件注册后按 `priority` 逆序执行（数值越大越先执行）
- 默认情况下：插件 hook 的返回值会被忽略；如果返回了非 None，会发出 RuntimeWarning（避免“你以为返回值会生效”这种隐性 bug）
- 可选 short-circuit：
  - `PluginManager(short_circuit=True, short_circuit_events=[...])`
  - 只对指定 event 允许“第一个非 None 返回值”短路后续插件
  - 适合做“候选过滤/替换”这类需要决定权的 hook（但建议优先做成 adapter，而不是在 plugin 里改控制流）

### 15.3 插件性能剖析（profile）

实现：`plugins/base.py`

- PluginManager 会对每个 hook 计时，并累计到插件实例的 `plugin._profile`：
  - `total_s`：累计耗时
  - `events[event_name]`：分事件耗时
- ModuleReportPlugin 会把这些计时写到 `modules.json`（见第 16 节）

### 15.4 “算法插件”识别（is_algorithmic）

实现：`plugins/base.py`、`plugins/ops/module_report.py`

- `plugin.is_algorithmic=False`（默认）：记录/导出/可视化/胶水类插件
- `plugin.is_algorithmic=True`：会影响搜索行为的插件（elite、restart、archive、region 等）
- `plugin.get_report()`：算法插件可返回一段小的 dict 摘要，用于审计/复现

## 16. 运行产物与文件格式（schema 参考）

本节把“每个产物长什么样、字段是什么意思”写清楚，保证后续写脚本汇总/画图不会靠猜。

### 16.1 BenchmarkHarnessPlugin 输出格式

实现：`plugins/ops/benchmark_harness.py`

CSV：`{output_dir}/{run_id}.csv`
- 字段（固定列）：`run_id, step, elapsed_s, eval_count, throughput_eval_s, best_score, phase, pareto_archive_size`
- 写入时机：`on_generation_end`
- 写入频率：`log_every`（默认每代写一行）
- flush 策略：`flush_every`（默认每 10 行 flush）

JSON：`{output_dir}/{run_id}.summary.json`
- 核心字段：`run_id, status, steps, elapsed_s, eval_count, throughput_eval_s, best_score, phase, pareto_archive_size, seed`
- 兼容字段：`artifacts`（如果其他插件往 `result["artifacts"]` 注入路径，summary 会把它附带出来）

工程注意：
- 插件会在 `on_solver_init` 里（可选）设置 `random.seed` / `np.random.seed`，并尝试把 seed 写回 `solver.benchmark_seed`
- `best_score` 的读取策略是多路 fallback：优先读 solver 公开字段，其次读 shared_state，最后从 objectives + violation 推导（见 `_read_best_score`）

### 16.2 ModuleReportPlugin 输出格式

实现：`plugins/ops/module_report.py`

modules.json：`{output_dir}/{run_id}.modules.json`
- 顶层结构（示意）：
  - `solver.class`
  - `adapter.class`
  - `pipeline.class`（可空）
  - `bias_module.class`（可空）
  - `plugins[]`：每个插件包含：
    - `name, class, enabled, priority, is_algorithmic`
    - `time_total_s, time_events_s`
    - `report`（可选：仅对 is_algorithmic 且实现了 get_report 的插件）
  - `parallel`：从 solver 上读取的并行配置影子字段（见 `_collect_modules`）
  - `metadata.run_id/timestamp`

bias.json：`{output_dir}/{run_id}.bias.json`
- 顶层字段：
  - `enabled`：bias_module 是否存在且启用
  - `total_contribution`：累计贡献（按 Bias 的 `total_contribution` 求和）
  - `biases[]`：每个 bias 的 statistics（由 bias 本身的 `get_statistics()` 决定）
  - `metadata.run_id/timestamp`

bias.md（可选）：`{output_dir}/{run_id}.bias.md`
- 目的：人读报告，用于把 bias 的 contribution/usage/weight 做成表格

## 17. 并行评估：参数、后端与失败策略（细节参考）

### 17.1 ParallelEvaluator 的参数面

实现：`utils/parallel/evaluator.py`

核心参数（以 `ParallelEvaluator(...)` 为准）：
- `backend`: `"process" | "thread" | "joblib" | "ray"`（ray/joblib 取决于可选依赖）
- `max_workers`: 默认会基于 CPU 核心数；建议在外层 wiring 固化默认值
- `chunk_size`: batch 粒度（影响负载均衡与 IPC 开销）
- `enable_load_balancing`: 是否启用更均衡的任务分发
- `retry_errors/max_retries`: 单个个体失败是否重试（工程上用于规避偶发错误）
- `precheck/strict/fallback_backend`: 工程护栏（序列化检查失败时的行为）
- `problem_factory`: 子进程内构造 problem（Windows/进程后端更推荐）
- `context_builder/extra_context`: 控制并行环境下传入 bias 的最小 context

### 17.2 with_parallel_evaluation：无侵入集成方式

实现：`utils/parallel/integration.py`

- 包装方式：
```python
from nsgablack.core.blank_solver import SolverBase
from nsgablack.utils.parallel import with_parallel_evaluation

ParallelBlank = with_parallel_evaluation(SolverBase)
solver = ParallelBlank(problem, enable_parallel=True, parallel_backend="process", parallel_max_workers=12)
```
- 设计取舍：
  - 不改 solver 基类，只 override `evaluate_population`
  - 并行开关与参数通过 `ParallelizedSolver.__init__` 注入
  - `min_population_for_parallel` 用于避免“小种群开线程/进程池得不偿失”

### 17.3 并行下的“可复现”边界

当前版本的明确边界：
- 并行评估主要保证“结果可用、错误可控”；对跨进程严格 bit-level 复现不做强承诺
- 如果你需要强复现：
  - 固定 seed
  - 尽量使用 thread 后端（避免进程调度差异）
  - `problem.evaluate` 内部不要依赖全局随机或隐式外部状态
  - bias/repair 若依赖随机，同样需要显式 seed（放进 context 或模块内部）

## 18. Context：最小 schema、键约定与扩展规则

### 18.1 最小 schema（并行/串行共用）

实现：`utils/context/context_schema.py`

最小字段：
- `generation`（可空）
- `individual_id`（必填）
- `constraints`（list[float]）
- `constraint_violation`（float）
- `seed`（可空）
- `metadata`（可空 dict）

并行评估里会把 extra 合并进 context（见 `build_minimal_context(..., extra=...)`）。

### 18.2 键约定（避免“各写各的”）

实现：`utils/context/context_keys.py`

工程规则：
- 统一 key 名称与含义（例如 generation/seed/constraint_violation 等）
- 不要在核心路径里塞“业务大对象”（尤其是不可序列化对象），需要时用 `problem_factory` 或在主进程侧补充 context

## 19. 约束：输入形态与统一输出

实现：`utils/constraints/constraint_utils.py`

工程目标：把业务侧五花八门的约束形态，收敛为统一的两件事：
- `constraints`: `np.ndarray`（可能为空）
- `violation`: `float`（可排序的违反程度）

工程护栏：
- 约束计算异常不会直接炸整个 run（以“失败个体”策略处理，见并行评估的异常隔离）

## 20. CLI 与可发现性（catalog 的工程实现）

CLI 入口：
- `python -m nsgablack ...` 或安装后 `nsgablack ...`
- 实现：`__main__.py`

Catalog：
- 注册与查询：`catalog/registry.py`
- 运行时只在需要时 import entry 的 `import_path`，避免 catalog 初始化就触发一堆副作用

工程取舍：
- CLI 保持最小，只做 discoverability（where is X），避免把“跑实验”也塞进 CLI 导致需求爆炸

## 21. 开发工具链（格式化、类型检查、测试）

### 21.1 工具与配置落点

实现/配置：`pyproject.toml`

- 格式化：`black`
- 静态检查：`flake8`（依赖里有，但是否启用以你的工作流为准）
- 类型检查：`mypy`
- 测试：`pytest`（并带 markers 与 coverage 配置）

### 21.2 推荐命令（开发者本地）

```powershell
python -m pip install -e .[dev]
python -m pytest
python -m black .
python -m mypy .
```

说明：
- `pytest` 的默认配置来自 `pyproject.toml` 的 `[tool.pytest.ini_options]`
- markers 用于区分快慢/集成/单测：`slow/integration/unit/...`

## 22. Windows 工程细节（编码、路径与多进程）

### 22.1 文档乱码与 BOM

- 本仓库部分 Markdown 使用 UTF-8 BOM，以改善 Windows PowerShell 下的显示兼容性
- Python 源码建议保持 UTF-8（不强制 BOM），但要避免混入本地 ANSI 编码导致注释/字符串乱码

### 22.2 多进程 spawn 的工程影响

- Windows 默认是 spawn：子进程会重新 import 包，首次会慢
- 推荐策略：
  - 让 `problem` 可通过 `problem_factory` 在子进程构造（避免传不可序列化对象）
  - 大对象避免通过 IPC 往返（chunk_size 与返回数据结构要控制）

### 22.3 路径与中文目录

本仓库路径包含中文目录名时的工程建议：
- 尽量使用 Python 的 `pathlib.Path` 或 `os.path.abspath` 生成路径
- 所有落盘文件显式 `encoding="utf-8"`（已在关键插件中遵守）
