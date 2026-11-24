# 可学习卷积组件训练

这是 learnable_conv_component_search Project 下的独立标准 Case。规范装配入口为 [build_solver.py](build_solver.py)，运行入口为 [run_solver.py](run_solver.py)。

LearnableConvTrainingCase 接收 config、bundle、label。bundle 声明组件路径、图像与卷积核形状、系数、步长、padding 和 pooling；未知 overrides 会被拒绝。

具体语义实现见 [组件源码](evaluation/trainer.py)。输入通过 component_overrides 与正式 Case 请求传递；资源由 Project L0 注入 ResourceContext，本 Case 不发放全局资源。

从仓库根目录检查装配：

```powershell
python -m nsgablack project doctor --path examples/cases/learnable_conv_component_search/cases/learnable_conv_component_training --strict --build --format json
```

--build 会调用 builder，不执行训练或评估。真实运行需满足该组件声明的数据、Provider 与 backend 依赖；不能用装配通过代替结果正确性或性能验证。

