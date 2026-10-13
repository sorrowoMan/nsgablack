# MOEA/D 方向子池与 VNS 精修

本例装配 MOEA/D + GA + VNS：MOEA/D 自动产生 100 个方向投影子池，四个 VNS 实例合计随机处理其中 20 个方向，然后结果返回 MOEA/D 竞争。GA 的种群独立，不在 adapter1 的方向选择范围内。

组件包括 TwoCenters 双目标 Problem、共享 UniformInitializer / ContextGaussianMutation / ClipRepair、StrategyRouterAdapter、MOEADAdapter、NSGA2Adapter、VNSAdapter 和 Solver 自带 SolutionPool。不额外装配 Bias、Evaluation Provider 或 Plugin。Case 消费 Project 提供的资源授权。

```powershell
python examples/cases/solution_pool/cases/moead_refinement/run_solver.py --check
python examples/cases/solution_pool/cases/moead_refinement/run_solver.py
```

主要装配见 `adapter/refinement.py`：

```python
moead = MOEADAdapter(name="adapter1", population_size=100)
selection = subpools.random(20, moead)  # 替换为 subpools.all(moead) 选择全部
task = PoolTaskSpec(selection, steps=3, output="refined")
```

`build_solver(config={"view_count": None})` 使用全部方向；directions、workers、local_steps、max_steps、seed 可配置。默认 25 个提交步覆盖随机 20 方向的完整流程；选择全部方向需相应增加步数预算。steps 包含起点基准评估后的更新，每步可能评估多个邻域候选。

每个任务固定起点版本、方向权重与参考点，起点和邻域均通过原 Problem 求双目标，再投影供 VNS 比较。母池保存原始双目标；返回候选由 MOEA/D 按当前方向与替换上限决定成员。输出包含已接纳提案，不保证全部都是局部改进。本例验证装配机制，不宣称融合优于单算法。

同一候选可以占据多个方向，不复制候选身份；20 是方向数量，不是 VNS 实例数或并发资源数。任务的随机选择、比较参数和进度随现有事务/checkpoint 保存。

本轮验证（2026-10-13）：默认装配实际运行 25 个提交步、328 次评估，保留 100 个方向视图，选择 20 个不同方向，MOEA/D 返回任务、GA 初始化和四个 VNS 队列均完成，MOEA/D 反馈仍为双目标。18 项投影测试包含在 283 项通过的相关回归中；较慢的 300→30×100 分配测试在此前一轮通过，汇总复验未重复执行。未运行全仓全部测试，也未进行算法优越性 benchmark。

```powershell
python -m nsgablack project doctor --path . --strict --catalog-audit --profile framework-core --format json
python -m nsgablack project doctor --path examples/cases/solution_pool --strict --build --format json
```

两条 Doctor 均为 0 error、0 warning。根检查不执行全部 Case 的 build；上述 Project 的三个 Case 均已完成 build 检查。moead_refinement 没有独立 Case Catalog TOML，该项按明确作用域跳过，公开组件与例子登记在框架 Catalog；default 可见例子，framework-core 保留组件并过滤例子。
