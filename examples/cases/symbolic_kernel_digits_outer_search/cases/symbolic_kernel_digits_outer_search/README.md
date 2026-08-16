# symbolic_kernel_digits_outer_search

`symbolic_kernel_digits_outer_search` 保留的是一个 symbolic image-kernel outer search 壳。它的重点不是“当前仓库里已经完整可跑”，而是说明跨框架 nested Case 在新架构下应该怎样组织。

## 当前定位

这个 Case 想表达的是：

- `nsgablack` 负责 outer symbolic kernel structure search
- `mlblack` 负责 inner image classification evaluation
- Project / Case / Scaffold / L0 substrate 负责编排和资源授权

当前仓库中并没有随仓附带的内层 `symbolic_kernel_digits_classification` 标准 Case，因此这里属于迁移保留材料。

## 正确的架构读法

- `build_solver.py` 是 outer Case 的标准组装入口
- `run_solver.py` 是 outer Case 的本地 CLI 入口
- inner evaluation 不应再通过旧私有 demo surface 拼接
- 应先恢复内层 `mlblack` 标准 Case，再由 Project 层以标准方式短路调用

## 目录口径

不要再把这里理解成旧式 `case_scaffold` 教学结构。现在应当以标准 Case 目录为准：

| 路径 | 作用 |
|---|---|
| `build_solver.py` | 标准 Case 组装入口 |
| `run_solver.py` | Case 本地 CLI / 调试入口 |
| `problem/` | outer kernel problem、objective、constraint、inner-task contract |
| `pipeline/` | outer kernel genome 的表示与流转 |
| `adapter/` | outer search strategy |
| `bias/` | prior / soft guidance |
| `plugins/` | bridge、timeout、tracking、observability |
| `evaluation/` | outer evaluation surface |
| `runtime/` | Case 级 requirement / audit |

## 迁移条件

要让它重新成为正式案例，至少需要满足：

1. 补回内层 `symbolic_kernel_digits_classification` 标准 Case。
2. 通过 Project 层显式声明资源并发放 `ResourceContext`。
3. outer/inner 之间只通过标准 Case surface、artifact/result payload 和 `component_overrides` 通信。
4. 不在文档、脚本或默认值里写死本地 GPU 设备号。

## 结论

这个案例仍然有架构价值，但它当前展示的是“迁移目标形态”，不是已经完全收束的成品示范。
