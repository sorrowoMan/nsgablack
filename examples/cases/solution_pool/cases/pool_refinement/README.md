# 子池驱动的 GA + VNS 精修

标准 Case，入口为 `build_solver.py` / `run_solver.py`。示例使用单目标二次函数，演示候选交接与算法结构隔离，不是性能基准。

1. NSGA-II 建立 20 成员种群并发布首批候选。
2. 阶段策略进入 `refine`；细尺度、粗尺度两个 VNS 角色各自选出已提交候选中最好的 20 个，每个角色由两个独立实例分担。
3. 每个起点先评估自身，再执行一批邻域搜索，共两次接纳更新。四个实例属于逻辑角色，本例没有开启四线程执行。
4. 送评并接纳的起点与邻域候选按引用进入 `refinement/refined` 子池。子池不保证其中每一条都是改进解。
5. 阶段策略进入 `return`，NSGA-II 重新评估返回候选，用自己的环境选择决定替换；输入分批消费完毕后回到普通搜索。

`adapter/refinement.py` 只定义选择、阶段和装配策略；`PoolTaskAdapter` 承担通用交接、任务进度和恢复。VNS 通过共享管线中的 `ContextGaussianMutation` 消费自己的邻域尺度。`steps` 含基准求值，不是裸评估次数，也不是 Solver 的总代数。

```powershell
python examples/cases/solution_pool/cases/pool_refinement/run_solver.py --check
python examples/cases/solution_pool/cases/pool_refinement/run_solver.py
python -m nsgablack project doctor --path examples/cases/solution_pool --strict --build --format json
```

默认运行 25 个提交步骤。`config` 支持 `max_steps` 和 `pool_idle_steps`。作为 Project 一部分执行时，L0 由 `project_config.py` 授权；本 Case 不创建资源授权者。

完整契约见 [解池文档](../../../../../docs/architecture/SOLUTION_POOL_CN.md)。当前通用精修入口支持显式声明池初始化及搜索重启的 Adapter；已覆盖 SA/VNS。NSGA-II/III 支持池初始化和返回竞争。MOEA/D 的子问题比较与目标槽位绑定尚未接入，不能仅更换类名宣称完成。
