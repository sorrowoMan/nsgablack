# sa_valley：SA 独立 Case

目标 `(x0+1.5)^2 + 4*(x1-0.75)^2`，盒 `[-4,4]^2`；最优点 `[-1.5,0.75]`，最优值0。

Problem 在 problem/valley.py；Pipeline 在 pipeline/main.py；SA与初始化/变异组件装配在 adapter/search.py；唯一 Solver 装配入口是 build_solver.py。

默认种子29、40次提交、每批1。SA先评估起点，然后使用降温与Metropolis接受；ContextGaussianMutation只产生邻域提案。没有自定义Bias/Plugin。

独立运行 `python cases/sa_valley/run_solver.py`；与DE各有自己的Problem/Solver/Unit/解池，不共享母池。跨Case并发解释见[Project说明](../../README.md)。
