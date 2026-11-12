# de_bowl：DE 独立 Case

目标 `(x0-1)^2 + (x1+2)^2`，盒 `[-4,4]^2`；最优点 `[1,-2]`，最优值0。

Problem 在 problem/bowl.py；Pipeline 在 pipeline/main.py；DE与初始化组件装配在 adapter/search.py；唯一 Solver 装配入口是 build_solver.py。

默认种子17、种群12、每批12、16次提交。没有自定义 Bias/Plugin。DE内置差分/交叉与贪心替换，ClipRepair只负责问题边界。

独立运行 `python cases/de_bowl/run_solver.py`；与另一个Case并发应使用Project入口。跨Case资源授权和并发解释见[Project说明](../../README.md)。
