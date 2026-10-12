# 符号卷积核数字识别训练

这是 symbolic_kernel_digits_outer_search Project 下的独立标准 Case。规范装配入口为 [build_solver.py](build_solver.py)，运行入口为 [run_solver.py](run_solver.py)。

SymbolicKernelDigitsTrainingCase 接收 config、bundle、label。默认使用 digits、ridge 和 NumPy 配置；bundle 保留卷积系数与 symbolic_kernel_weights。未知 overrides 会被拒绝。

具体语义实现见 [组件源码](evaluation/trainer.py)。输入通过 component_overrides 与正式 Case 请求传递；资源由 Project L0 注入 ResourceContext，本 Case 不发放全局资源。

从仓库根目录检查装配：

```powershell
python -m nsgablack project doctor --path examples/cases/symbolic_kernel_digits_outer_search/cases/symbolic_kernel_digits_training --strict --build --format json
```

--build 会调用 builder，不执行训练或评估。真实运行需满足该组件声明的数据、Provider 与 backend 依赖；不能用装配通过代替结果正确性或性能验证。

