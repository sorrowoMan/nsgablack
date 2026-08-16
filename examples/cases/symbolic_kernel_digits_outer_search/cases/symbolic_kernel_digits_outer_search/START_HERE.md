# START_HERE

## 1) 这个 case 验证什么

`symbolic_kernel_digits_outer_search` 是一个 compatibility outer-search scaffold，用来保留 symbolic image-kernel 外层搜索设计。

- nsgablack 搜索 symbolic kernel/object structure。
- inner evaluation 必须通过一个标准 mlblack Case surface 接入；当前仓库没有随附该 inner case，因此不要把本目录当作权威可运行新示例。
- 主指标是 strict accuracy-first loss，并包含 gap、complexity、prior penalties。

结构、指标和预期信号见 `README.md`。

## 2) 推荐状态

优先参考当前标准跨框架文档：

- `docs/standard_scaffold_tutorial/05_cross_framework_coordination.md`
- `docs/standard_scaffold_tutorial/07_nested_orchestration_standard.md`

如果迁移这个 case，先创建或恢复内层 `symbolic_kernel_digits_classification` 标准 Case，再由 Project L0 发放 `ResourceContext`。不要在命令行或 case 默认值中写死本地 GPU 设备号。

## 3) 关键指标

| 指标 | 含义 |
|---|---|
| `strict_primary_loss` | Accuracy-first scalar objective。 |
| `classification_error` | 原始分类错误率。 |
| `generalization_gap` | Train/test gap。 |
| `feature_complexity` | Kernel feature complexity。 |
| `kernel_prior_penalty` | Preferred-prior violation penalty。 |

## 4) 预期信号

有效运行应该改善图像分类错误率，同时控制 gap、complexity 和 prior penalties。
