# ETF lane 评估

这是 etf_lane_outer_search Project 下的独立标准 Case。规范装配入口为 [build_solver.py](build_solver.py)，运行入口为 [run_solver.py](run_solver.py)。

build_pipeline 解析 config 与 component_overrides，输出 walkforward、lane_bundle；EtfLaneEvaluationCase 接收这些值和 ResourceContext。

具体语义实现见 [组件源码](pipeline/main.py)。输入通过 component_overrides 与正式 Case 请求传递；资源由 Project L0 注入 ResourceContext，本 Case 不发放全局资源。

从仓库根目录检查装配：

```powershell
python -m nsgablack project doctor --path examples/cases/etf_lane_outer_search/cases/etf_lane_evaluation --strict --build --format json
```

--build 会调用 builder，不执行训练或评估。真实运行需满足该组件声明的数据、Provider 与 backend 依赖；不能用装配通过代替结果正确性或性能验证。

