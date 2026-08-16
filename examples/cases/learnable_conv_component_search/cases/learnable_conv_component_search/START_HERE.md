# START_HERE

## 1) 这个 case 验证什么

`learnable_conv_component_search` 是 compatibility outer-search scaffold，保留 nsgablack 对 mlblack learnable convolution component 的 outer structure search 设计。

- nsgablack 搜索 kernel structure、stride、padding、pooling、output mode 和 symbolic basis terms。
- inner evaluation 必须通过标准 mlblack Case surface 评估/细化选中 component。
- 当前仓库没有随附被引用的 `learnable_conv_component_demo` inner case，因此不要把本目录当作权威可运行新示例。
- Objectives 平衡 test RMSE、generalization gap、feature complexity 和 kernel recovery。

结构、指标和预期信号见 `README.md`。

## 2) 推荐状态

优先参考当前标准跨框架文档：

- `docs/standard_scaffold_tutorial/05_cross_framework_coordination.md`
- `docs/standard_scaffold_tutorial/07_nested_orchestration_standard.md`

迁移这个 case 时，先创建或恢复内层 `learnable_conv_component_demo` 标准 Case，再由 Project L0 发放 `ResourceContext`。

## 3) 关键指标

| 目标 | 含义 |
|---|---|
| `test_rmse` | Held-out prediction error。 |
| `generalization_gap` | Overfit/generalization signal。 |
| `feature_complexity` | 选中 component 的结构成本。 |
| `kernel_recovery_penalty` | 是否恢复目标 kernel structure。 |

## 4) 预期信号

有效运行应该改善 test error 和 kernel recovery，同时控制 component complexity。
