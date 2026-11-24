# PhiBundle 图像评估

这是 phi_bundle_image_search Project 下的独立标准 Case。规范装配入口为 [build_solver.py](build_solver.py)，运行入口为 [run_solver.py](run_solver.py)。

PhiBundleEvaluationCase 接收 config、bundle、label。默认数据配置为 digits；bundle 描述 lane、特征上限、相关性阈值及源数量。未知 overrides 会被拒绝。

具体语义实现见 [组件源码](evaluation/trainer.py)。输入通过 component_overrides 与正式 Case 请求传递；资源由 Project L0 注入 ResourceContext，本 Case 不发放全局资源。

从仓库根目录检查装配：

```powershell
python -m nsgablack project doctor --path examples/cases/phi_bundle_image_search/cases/phi_bundle_image_evaluation --strict --build --format json
```

--build 会调用 builder，不执行训练或评估。真实运行需满足该组件声明的数据、Provider 与 backend 依赖；不能用装配通过代替结果正确性或性能验证。

