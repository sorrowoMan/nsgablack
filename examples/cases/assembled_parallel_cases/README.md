# 完整 Project：DE 与 SA 的两个独立 Case 并发

详细代码阅读：[项目全部源码](PROJECT_CODE.md) · [框架组件源码索引](COMPONENTS.md) · [四种完整装配对照](../ASSEMBLED_PROJECTS_GUIDE_CN.md)。

这个例子回答：**两个算法各自求解不同的问题，怎样放进同一个标准 Project，同时运行，并确认资源授权和结果没有混在一起？**

这里有两个完整 Case：DE 求解球面函数，SA 求解二次谷地。每个 Case 都有自己的 Problem、Pipeline、Adapter、Solver、SolutionPool 与结果。Project 负责启动它们、授权资源、等待结果和发布结果。

这是跨 Case 的真实并发。它没有候选交接，不构成 DE+SA 融合；也没有把两个算法的 Unit 拼在一个种群里。

实际运行记录见 [RESULTS.md](RESULTS.md)，机器可读简表见 [results/summary.json](results/summary.json)。项目代码快照见 [PROJECT_CODE.md](PROJECT_CODE.md)。

## 1. 先运行，再顺着结果读代码

在仓库环境已经安装 nsgablack/blackbase 的前提下：

```powershell
Set-Location "C:\Users\hp\Desktop\nsgablack\examples\cases\assembled_parallel_cases"

# 只检查正式 Project/Case 装配和授权；不求解
python run_project.py --check --build-check

# 真实并发执行两个 Case，保存正式结果并生成解释报告
python run_and_report.py

# 正式入口本身也可以运行；它不额外整理本例的 RESULTS.md
python run_project.py

# 使用已有 ProjectRunResult 重新核对报告，不再求解
python run_and_report.py --report-only
```

仓库根的正式 Doctor 命令：

```powershell
python -m nsgablack project doctor --path examples/cases/assembled_parallel_cases --strict --build --catalog-audit --profile framework-core --format json
```

`--build` 会调用 builder；不是纯文本扫描。Doctor 的通过范围与真实并发求解不同，两者都应看。

## 2. 完整结构及每个位置的职责

```text
assembled_parallel_cases/
  .gitignore
  _bootstrap.py
  project_config.py             # 两个 Case 的并发 stage + 唯一 L0 资源授权
  run_project.py                # 正式 Project CLI 的薄入口
  run_and_report.py             # 调正式 execute_project；只读核对并生成本例报告
  README.md
  RESULTS.md                    # 真实运行后生成
  PROJECT_CODE.md               # 项目代码集中阅读快照
  results/
    project_result.json         # execute_project(...).as_dict() 完整返回
    timing.json                 # 本例入口墙钟测量，绑定同一 project_run_id
    summary.json
    cases/
      de_bowl.json
      sa_valley.json
  cases/
    __init__.py
    de_bowl/
      .case
      __init__.py
      README.md
      config.py
      build_solver.py
      build_trainer.py          # build_solver 的薄别名
      run_solver.py
      run_trainer.py            # run_solver 的薄别名
      problem/
        __init__.py
        bowl.py
      pipeline/
        __init__.py
        main.py
      adapter/
        __init__.py
        search.py
      catalog/entries/problem.toml # 本地自定义Problem可发现性；不污染框架Catalog
      bias/__init__.py
      plugins/__init__.py
      evaluation/__init__.py
      runtime/__init__.py
      solver/__init__.py
    sa_valley/
      ...同一标准结构...
      problem/valley.py
      pipeline/main.py
      adapter/search.py
```

`bias/`、`plugins/`、`evaluation/`、`runtime/`、`solver/` 是本例没有额外实现的正式扩展位置，因此保留空包。不是“每个目录都要写一个组件”。

不复制框架的并发执行器、资源分配器、图导出器或检查点实现。它们由安装的 nsgablack/blackbase 提供。

## 3. 两个 Problem 完全独立

### DE 的球面问题

源码：[bowl.py](cases/de_bowl/problem/bowl.py)。

```text
f_de(x) = (x0 - 1)^2 + (x1 + 2)^2
x0, x1 ∈ [-4, 4]
```

每一项非负，`[1, -2]` 令两项同时为零，所以解析最优值为 0。Problem 只说明值是什么意思，不知道 DE 如何产生 trial 或淘汰成员。

### SA 的二次谷地

源码：[valley.py](cases/sa_valley/problem/valley.py)。

```text
f_sa(x) = (x0 + 1.5)^2 + 4 * (x1 - 0.75)^2
x0, x1 ∈ [-4, 4]
```

解析最优点是 `[-1.5, 0.75]`，最优值为 0。系数 4 让第二个坐标方向更陡；这个问题和 DE 的问题不是同一份评估定义。

两个 Problem 都显式返回盒边界的原始违反量。Pipeline 修复与 Problem 约束含义不同：前者处理候选，后者声明如何测量违反。不能因为修复一般有效就省去评估含义。

## 4. Pipeline 为什么很薄

两个 Case 各构造自己的 `RepresentationPipeline(repair=ClipRepair(-4, 4))`。同一种组件类可以复用，但这里的对象与 Solver 状态是独立的。

框架源码：[RepresentationPipeline](C:/Users/hp/Desktop/nsgablack/representation/base.py)、[ClipRepair](C:/Users/hp/Desktop/nsgablack/representation/continuous.py)。

本例不需要候选编码，也不需要把数组解码成另外一种类型。Unit 的构造/恢复也不是候选编码。DE 的种群结构与 SA 的轨迹结构分别由各自 Adapter 的 UnitBinding 按需建立。

修复在正常提案边界进行；没有在 `adapter/search.py` 手工再调用一次 repair。控制面保持提案 token 并执行原所有者对账，之后才求值。

这里不额外装配 UnitRepair 或 JointRepairPolicy。盒修复能被两个算法当前的提案替换契约接受，并不代表任何图搜索/信赖域算法都可照抄。

## 5. DE 的装配与实际行为

本地工厂：[adapter/search.py](cases/de_bowl/adapter/search.py)。

```python
DifferentialEvolutionAdapter(
    name="de_bowl",
    initializer=UniformInitializer(-4.0, 4.0),
    config=DEConfig(
        population_size=12, batch_size=12,
        differential_weight=0.7, crossover_rate=0.9,
        strategy="rand1bin",
    ),
)
```

- 初始化：显式装配 UniformInitializer；第一次实际提案建立初始种群并送评。
- 变化：本例使用 DE 内置差分与交叉规则。没有为了填接口而装一个 GaussianMutation。
- 选择：trial 与原目标槽位按照 DE 自己的比较规则进行贪心替换。
- 修复：共享的正常问题修复边界处理越界 trial，DE 保留目标索引和比较基线，对修复后的候选使用正式反馈。

四类行为不是必须每步严格依次执行的四个全局阶段。这里的环境状态属于 DE 的 DifferentialPopulationUnit，不属于 Project。

框架源码：

- [DifferentialEvolutionAdapter / DEConfig](C:/Users/hp/Desktop/nsgablack/adapters/differential_evolution/adapter.py)
- [UniformInitializer](C:/Users/hp/Desktop/nsgablack/representation/continuous.py)
- [结构 builders](C:/Users/hp/Desktop/nsgablack/representation/structure_builders.py)
- [UnitBackedAdapter](C:/Users/hp/Desktop/nsgablack/adapters/unit_backed.py)

固定种子 17，16 次提交。第一次 12 个初始候选，之后 15 次各 12 个 trial，因此正常完整接纳路径为 `12 + 15×12 = 192` 次求值。报告核对实际计数；不从配置直接编造结果。

`population_size=12` 是 DE 自身结构容量，`batch_size=12` 是它每步 trial 数；它们都不是整个 Project 的解池容量。

## 6. SA 的装配与实际行为

本地工厂：[adapter/search.py](cases/sa_valley/adapter/search.py)。

```python
SimulatedAnnealingAdapter(
    name="sa_valley",
    initializer=UniformInitializer(-4.0, 4.0),
    mutator=ContextGaussianMutation(base_sigma=0.65),
    config=SAConfig(
        batch_size=1, initial_temperature=1.0,
        cooling_rate=0.94, min_temperature=1e-6,
        base_sigma=0.65, random_seed=29,
    ),
)
```

第一次先建立已评估的起点基准；此步不会把邻居分数错绑定给未评估起点，也不降温。后续从当前点提出邻居，温度影响局部 `mutation_sigma` 与 Metropolis 接受。`ContextGaussianMutation` 只生成邻居，不能决定是否接受。

SA 可以接受变差的当前点。最终正式最好候选与“结束时当前点”是不同问题，本例报告使用正式 SolverResult 的最好候选，不能从最后一个邻居猜结果。

固定种子 29，40 次提交，batch_size=1，所以正常路径为 40 次求值，包含起点基准。

框架源码：

- [SimulatedAnnealingAdapter / SAConfig](C:/Users/hp/Desktop/nsgablack/adapters/simulated_annealing/adapter.py)
- [ContextGaussianMutation / UniformInitializer](C:/Users/hp/Desktop/nsgablack/representation/continuous.py)
- [轨迹结果与精确引用](C:/Users/hp/Desktop/nsgablack/adapters/pool_results.py)

## 7. Case 的 build_solver 为什么这么短

[DE 装配](cases/de_bowl/build_solver.py) 与 [SA 装配](cases/sa_valley/build_solver.py) 都只做四件事：

1. 通过本地工厂构造 Problem、Pipeline、Adapter。
2. 构造 ComposableSolver，并传入 Project 发下来的 ResourceContext。
3. 设定随机种子和该 Case 的逻辑提交预算。
4. 接受正式 `component_overrides` 扩展入口，返回 Solver。

没有自写优化循环，没有线程池，也没有在 Case 内再分配全局资源。`bias_module` 没有传入，默认不启用 Bias；本例没有评估 Provider 接管或自定义 Plugin。

这样保持了“想了解算法装配，打开 adapter/search.py；想改问题，打开 problem/；想改并发，打开 project_config.py”的分工。

## 8. Project 如何产生真实并发

查看 [project_config.py](project_config.py)：

```python
L0["offer"]["threads"] = 2
L0["policy"]["max_workers"] = 2
stage["policy"] = "parallel"
stage["max_workers"] = 2
```

配置文件实际定义完整字典；上面只是把关键字段摘出来解释。两个 Case 各请求 `threads=1, workers=1`。

正式 Project runner 读取 stage，使用共享 BlackBase 的跨 Case 并发执行路径；本地并发路径使用隔离的 worker 进程。每个 Case 有不同 case_run_id、lease_id 和 namespace。上层 L0 的授权总量允许两者同时持有资源。

L0 中的 `execution_backend="local"` 指本地执行域，并不意味着把 stage 改成串行；stage 的 `policy="parallel"` 决定这里的并发关系。

源码入口：

- [nsgablack Project facade](C:/Users/hp/Desktop/nsgablack/project/project_runner.py)
- [BlackBase Project runner](C:/Users/hp/Desktop/blackbase/src/blackbase/project/project_runner.py)
- [BlackBase Project L0](C:/Users/hp/Desktop/blackbase/src/blackbase/project/runtime.py)
- [ResourceContext / ResourcePolicy](C:/Users/hp/Desktop/blackbase/src/blackbase/resources/model.py)
- [CaseRunResult](C:/Users/hp/Desktop/blackbase/src/blackbase/project/execution.py)

两个子 Solver 都只看到自己的 ResourceContext。threads=1 是授权与组件绑定信息，不能仅凭这个字段声称第三方库在操作系统层永不额外开线程。

## 9. 这和一个 Case 里并列两个 Adapter 有什么区别

本例的两个 Case 各有独立 Problem、运行预算、SolutionPool、结果发布与故障边界。它们没有共同的母池。Project 并发调度的是完整 Case。

一个 Case 内用 Router/Composite 组织多个 Adapter，则通常共享该 Solver 的问题、控制面与池，再通过明确任务/视图交接；逻辑同时出提案也不自动等同于两个隔离进程执行。

因此本例不能用来声称“GA 与 VNS 已实现池交接”或“DE 与 SA 已融合”。它演示另一种同样正式的组合层级：完整求解任务的并发。

如果以后要让 DE 结果进入 SA，必须另设串行阶段和 Artifact/结果输入协议，或改为同一 Case 内的池任务装配；不能把一个 Case 的私有内存池对象传给另一个 worker 当全局共享状态。

## 10. 为什么 report 不是第二个 runner

[run_and_report.py](run_and_report.py) 的执行只有一次：

```python
project = execute_project(ROOT).as_dict()
```

后续全是对正式返回值的读取：保存原值、检查运行身份、取出最好候选、核对资源绑定与时间重叠。它既不调用 Adapter.propose/update，也不启动 ProcessPoolExecutor，更不替代 Project 的异常、取消和发布协议。

结果的身份来自同一次 ProjectRunResult。`timing.json` 明确绑定 project_run_id；`--report-only` 拒绝把另一次运行的入口耗时混进当前结果。

`results/cases/de_bowl.json` 和 `sa_valley.json` 分开写，避免两个 Case 往同一个结果文件覆盖。这里没有在子进程中装一个同名输出 Plugin。

## 11. 并发证据怎样算

对两个 Case 正式开始/结束时刻，重叠秒数是：

```text
max(0, min(end_de, end_sa) - max(start_de, start_sa))
```

报告脚本要求结果大于零，否则拒绝写“本次并发已演示”的成功摘要。没有用 sleep 人工制造重叠。

时间区间包含 Case 的构建、Solver 运行、清理和发布。它证明生命周期重叠，不能精确证明两个 evaluate 在同一纳秒同时占 CPU。若要评估加速比，需要相同工作负载、串行基线、多次运行和适当计时；本例没有执行那种 benchmark。

Windows worker 启动、框架导入、证据归档和结果 seal 对这个很便宜的函数占比可能很高。小问题的并发不保证更快，这不影响它作为装配和资源边界的例子。

## 12. 结果如何核对

报告脚本检查：

- Project 成功且恰好包含两个约定 Case。
- 两个 Case 成功，且 identity.project_run_id 属于同一返回值。
- grant 各为 1 线程/1 worker，binding.current 为真。
- namespace 与 lease_id 各不相同。
- 逻辑步数与实际求值次数符合所装配预算。
- 最后候选在盒内，解析重算与正式最好目标一致。
- 两个 Case 生命周期有正的交集。

解析重算是报告阶段的独立数学核对，不是重新调用 Solver.evaluate，不修改求值预算，也不冒充从持久 raw evidence 重建的审计记录。本例无 Bias，正式选择目标和原始目标一致。

有限预算结果通常不等于解析最优。两算法的问题与预算不同，不能用最终误差比较算法优劣。

## 13. 空扩展面意味着什么

本例没有故意塞满所有组件：没有 Bias，没有自定义生命周期 Plugin，没有外部评估 Provider，没有自定义 Unit 字段，也没有 checkpoint/resume 插件演示。

它仍使用框架内部的正式事务、候选身份、解池、运行进度、资源绑定和证据发布。这些基础设施不要求用户在每个 Case 重写。

要看“一个 Solver 内如何交接候选”，读兄弟例子 [assembled_ga_vns](../assembled_ga_vns/README.md)。这里更适合先理解 Project/Case 独立性和真正并发。

## 14. 本地 Catalog 与当前验证范围

每个 Case 的 `catalog/entries/problem.toml` 登记自己的自定义 Problem，包含导入路径、使用场景、装配例子和空 Context 读写声明。它们只属于该 Case 的本地发现范围，不写入框架全局 Catalog，也不要求部署数据库。

内置 ClipRepair、UniformInitializer、DE、SA 已由框架提供，本例不重复制造一套同名全局条目。Doctor 在相应 Case 的导入作用域核对本地索引，因此不会把另一个 Case 的 `problem/` 包误认成自己。

实际执行结果与具体命令记录应结合本目录 [RESULTS.md](RESULTS.md)、[validation.json](results/validation.json) 阅读。

本次真实运行：DE 16步/192次求值，目标约0.00999604；SA 40步/40次求值，目标约2.56046477；生命周期重叠20.654013秒。SA的小预算结果距离解析最优仍明显较远，保留这个结果供检查，没有筛选随机种子来营造收敛效果。严格Doctor含build与framework-core Catalog审计的最终信息数见validation.json；两项本地Problem索引在最终检查中实际读取。

`--check --build-check` 的 runtime_state.initializer/mutator 目前展示 Pipeline 槽位；本例显式绑定在 Adapter 上的初始化与 SA mutator 不能因这里显示 None 就判定没装配。真实装配代码和 get_operation_contract() 才是这些直接绑定的入口。该显示限制没有通过在例子里伪造输出绕过。

只读源码检查与正式 build 检查不能证明任意算法正确；本例求解也不能替代跨设备、外部后端、失败恢复和长期并发的全套测试。
