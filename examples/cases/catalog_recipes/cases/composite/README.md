# Composite：两个独立种群，每步统一送评

本 Case 将两个 NSGA2 实例的提案拼成一批，交给同一 Solver 求值，再把各自反馈交回原实例。它演示 CompositeAdapter 实际组合的对象：候选提案与反馈路由；两个实例仍各自维护种群和搜索结构。

## 这里到底装了什么

规范装配入口是 [build_solver.py](build_solver.py)，由外层 [Project 配置](../../project_config.py) 发放 1 线程、0 GPU 的 ResourceContext，并最多运行 2 个逻辑提交步。

- Problem 是现成 `QuadraticProblem`：二维候选 `(x0,x1)`，原始目标 `x0²+x1²`，一个最小化目标。
- 共享 [问题管线](pipeline/main.py) 提供 `[-2,2]` 初始化和边界修复。
- `wide` 是容量 4、每次提案 4 的 NSGA2，直属 `GaussianMutation(sigma=0.4)`。
- `narrow` 是另一个容量 4、每次提案 4 的 NSGA2，直属 `GaussianMutation(sigma=0.05)`。

两个变异器是不同对象，分别由实际 Adapter 持有；不把同一有状态算子同时绑定到两个实例。共享管线里的默认变异器不替代这两个直属绑定。`wide/narrow` 表示不同扰动尺度，不表示固定性能优劣。

## 一步怎么执行

Composite 按列表顺序调用 `wide.propose(...)`，再调用 `narrow.propose(...)`，把两份候选按该顺序拼接。本例每份 4 行，整批为 `(8,2)`。

随后由同一 Solver 做预算裁剪、问题修复、正式评估和接纳。未受到额外预算或接纳限制时，反馈目标矩阵为 `(8,1)`、违反量为 `(8,)`。Composite 记住各子实例的提案区间：前 4 行交回 wide，后 4 行交回 narrow。修复和部分接纳也沿同一来源映射路由，反馈中的语义 items 一起保留。

每个 NSGA2 只用自己的反馈更新自己的种群，分别留下至多 4 个已评估成员。Composite 不把两个种群做一次统一的非支配排序，不去重相同数值候选，也不共享可写排名。

这里的 propose 和 update 是同步、按顺序调用；Composite 没有建立线程或进程池。求值后端能否并行是 Solver/Provider/Project 的另外配置，不由 Composite 这个名字决定。本 Project 仅授予一个 CPU 线程。

## 怎样运行

在 nsgablack 仓库根目录使用正式 Project 入口：

```powershell
python examples/cases/catalog_recipes/run_project.py --no-record
```

当前 Project 的默认组只运行本 composite Case。`--no-record` 关闭 Project 运行清单持久化，不改变算法或接纳语义。

默认终端的 `project-runtime` 信息可核对 Project/Case、实际组件与生效资源绑定，进程退出码反映运行是否成功。完整结果可通过标准 `execute_project(...).case_results[0].output` 取得；当前结果含 `solve_status/best_solution/best_objectives/report` 等字段，没有顶层 population_state_mode 或种群分区字段。下面的分区 API 是程序式诊断方式，不是假定 CLI 已经输出同名字段。

## 两个结果分别从哪里读

多子 Composite 的权威模式是 `partitioned`。`solver.adapter.get_population_snapshot()` 返回 `None`，因为没有一份隐含合并的最终种群；使用：

```python
partitions = solver.adapter.get_population_partitions()
for partition in partitions:
    print(partition.partition_id)
    print(partition.population)
    print(partition.objectives)
    print(partition.violations)
    print(partition.candidate_tokens)
```

这里的 `solver` 必须是本次正式 Case 运行结束后仍保留的实例，不能在 CLI 已退出后凭空引用。每个 `PopulationPartition` 的候选、反馈和 token 行顺序对齐；本 Case 的两个 ID 应分别为 `child:0:wide/population` 和 `child:1:narrow/population`。

需要程序式诊断时，可以使用现有标准 Case 接口选择另一种运行方式。以下 `project_root` 是 `examples/cases/catalog_recipes` 目录，`resource_context` 由实际调用方传入有效资源上下文；这个函数会真正运行该 Case，然后只读分区，不另写算法循环：

```python
from blackbase.project import build_case, load_case_builder, run_case

def run_and_inspect(project_root, *, resource_context):
    builder = load_case_builder(project_root, "composite")
    solver = build_case(builder, resource_context=resource_context)
    result = run_case(solver)
    partitions = solver.adapter.get_population_partitions()
    return result, partitions
```

这个调用不负责全局资源授权；嵌入 Project 时继续传入 Project 发放的上下文。它是对同一规范 builder 的程序式运行与诊断，不是读取刚才另一个 CLI 进程的对象。选择一种方式运行即可，不要为读分区不加区分地重复执行搜索。

无 Bias 的本例中，可把各分区 `population` 的逐行平方和与其 `objectives[:,0]` 比较，并核对 `candidate_tokens` 数量等于成员行数。需要读原始池反馈时，用具体子 Adapter 的 `get_population_solution_refs(solver)` 取得有序引用，再调用 `solver.solution_pool.read_raw_feedback(refs)`；不要把根池历史误认为当前种群。

## 本次教学验收实际读到了什么

已通过正式 `nsgablack.project.project_runner.execute_project` 执行本 Project 一次，保留同一次 Case 实例作只读断言；没有另写搜索循环或修改运行时协议。结果为 Project `ok`、Case `succeeded`，2 个逻辑提交步、16 次候选求值。

`get_population_partitions()` 实际返回包含两个 `PopulationPartition` 的 tuple：

- `child:0:wide/population`：population `(4,2)`，objectives `(4,1)`，violations `(4,)`，4 个 candidate tokens，4 个有序池引用。
- `child:1:narrow/population`：同样为 `(4,2)/(4,1)/(4,)`，4 个 candidate tokens，4 个有序池引用。

两个实例的 algorithm_unit 是不同对象；两个分区都通过原始池反馈与逐行平方和目标核对。根 `get_population_snapshot()` 实际为 None，`solver.population_authority_mode` 为 `partitioned`。这些是运行中 API 的观测，不是默认 CLI 输出；未把随机得到的某个最佳值当作性能或收敛保证。

## 如果你想要的是 GA 后接 VNS 精修

把这两个 NSGA2 改成 `[NSGA2Adapter(), VNSAdapter()]`，只会让两个实例各自提案、各自消费反馈；不会自动把 GA 的种群交给 VNS。它们共享 Solver 的问题候选管线和 SolutionPool，并不表示共享种群或存在精修任务。

逐成员精修应参考正式 [assembled_ga_vns Project](../../../assembled_ga_vns/README.md)：那里显式使用 PoolTaskSpec、`subpools.all(ga)`、阶段调度和返回竞争。Composite 本身只有 `adapters/name/priority` 构造参数，没有线程数、角色权重、自动精修或通用冲突解决参数。

运行上下文投影中遇到重复字段名时，共享聚合器采用先写者保留；这只是观察字段合并规则，不是算法竞争或种群冲突解决策略。各子实例应使用独立名称，checkpoint 依赖列表顺序与名字恢复，不能恢复时随意交换顺序。
