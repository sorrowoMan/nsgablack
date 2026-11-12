# pool_recovery：一个完整的标准 Solver Case

语义是优化搜索，框架为 nsgablack。唯一装配入口是 [build_solver.py](build_solver.py)，运行入口是 [run_solver.py](run_solver.py)。Trainer 两个入口仅保留薄别名。

本 Case 接收 Project 传入的 ResourceContext，不直接申请全局线程／GPU。Project 配置一个线程、一个 worker，两个种群是独立逻辑搜索器。

本地组件如下：

- [problem/plateau.py](problem/plateau.py)：`max(0,x0²+x1²-1)`，盒约束 `[-2,2]²`。
- [pipeline/main.py](pipeline/main.py)：共享 ClipRepair，初始化／变化直接绑定实际 Adapter。
- [adapter/composition.py](adapter/composition.py)：SA → 两个私有种群 → 停滞恢复 → 返回竞争。
- [config.py](config.py)：默认八步演示的配额、容量、批量、阈值和随机种子。
- [plugins/trace.py](plugins/trace.py)：只读记录已提交行为与精确成员来源。
- [catalog/entries/components.toml](catalog/entries/components.toml)：Case 本地组件发现入口。

不装 Bias 或第三方评估 Provider；不写自己的 Solver 主循环。通用 PoolSearch／SA／NSGA-II／SPEA2 代码直接使用框架实现。

默认起点已经位于最优平坦区域。本例验证停滞触发与候选交接，不证明局部最优逃逸或质量收益。

从 Project 根目录运行 `python run_and_report.py` 可得到正式 Project 结果与已核对报告；完整解释见 [Project README](../../README.md)，实际结果见 [RESULTS](../../RESULTS.md)。
