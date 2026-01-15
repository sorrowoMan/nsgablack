# NSGABlack

<div align="center">

**偏置驱动的多目标优化生态框架**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

把算法策略与业务约束解耦 · 编码与算子模块化 · 智能策略可插拔复用

</div>

---

## 我该先看什么

- `START_HERE.md`：入口地图（按场景选入口）
- `QUICKSTART.md`：5-10 分钟上手
- `examples/multi_agent_bias_quickstart.py`：偏置 + 多智能体快速体验
- `docs/FRAMEWORK_OVERVIEW.md`：框架鸟瞰
- `docs/PROJECT_DETAILED_OVERVIEW.md`：完整特性与设计细节
- `docs/FRAMEWORK_DESIGN_QA.md`：关键质疑与回应
- `docs/TOOLS_INDEX.md`：工具/脚本索引

---

## 一句话核心

管线是“类型”，偏置是“操作”。Pipeline 决定搜索空间与可行性，Bias 决定策略与引导。

直觉表达：`Solution = f(Pipeline, Bias1, Bias2, ...)`

更完整的形式：`SolutionSet = Optimize(Problem, Pipeline, Biases, Solver, Budget)`

偏置化的收益：

- 迁移：问题换了，只需换 Pipeline 与少量 Bias，求解循环不动。
- 可控：更多可调参数意味着每个环节都能单独开关/微调，做局部消融不牵动其他逻辑。
- 沉淀：精调过的策略可抽象成 Bias 资产，后续问题直接复用。

---

## 快速入口表

| 目的                  | 命令/文件                                          | 预期产出/用途                    |
| --------------------- | -------------------------------------------------- | -------------------------------- |
| 冒烟验证              | `python examples/validation_smoke_suite.py`      | 基本功能跑通                     |
| 基准（ZDT/DTLZ/约束） | `python examples/benchmark_zdt_dtlz_igd_hv.py`   | `reports/benchmark/*.json/csv` |
| 连续偏置最小示例      | `python examples/simple_bias_example_no_viz.py`  | 看 Pareto 与约束惩罚             |
| 排列/TSP 最小示例     | `python examples/simple_tsp_demo.py`             | 看离散表征与路径收敛             |
| 多智能体 + 偏置体验   | `python examples/multi_agent_bias_quickstart.py` | 角色分工 + 偏置联动              |

---

## 架构图（Pipeline 决定空间，Bias 决定策略）

```text
Problem (objective/constraints)
        |
        v
Pipeline (encode/repair/init/variation) ---> Candidate Space (type & feasibility)
        |
        v
Solver Loop (NSGA-II / MOEA-D / MultiAgent.....)
  |   ^
  |   +---- Biases (sampling/constraint/score/selection/surrogate)
  |
  +--> Archive / History / Metrics
```

- MultiAgent：以角色协作方式替换/包裹 Solver Loop
- Surrogate：作为 Bias（预筛选/评分/替代评估）插入

---

## 最小示例（连续约束 + 离散/排列，一键跑）

**连续约束（工程类）**

```bash
python examples/simple_bias_example_no_viz.py
```

**离散/排列（TSP）**

```bash
python examples/simple_tsp_demo.py
```

---

## 基准结果（ZDT/DTLZ/约束类）

**运行命令**

```bash
python examples/benchmark_zdt_dtlz_igd_hv.py
```

**结果输出**

- `reports/benchmark/benchmark_results.json`
- `reports/benchmark/benchmark_results.csv`
- `reports/benchmark/benchmark_summary.csv`
- `reports/benchmark/benchmark_report.md`

**参考区间（默认参数、3 次运行、仅作 sanity check）**

> HV 当前仅支持 2 目标；3+ 目标建议用 IGD / Pareto 数 / 违约率等指标。

| 基准               | 主要指标          | 参考区间                                   |
| ------------------ | ----------------- | ------------------------------------------ |
| ZDT1               | IGD / HV / Pareto | IGD 1.3–2.6；HV 1.8–3.2；Pareto 20–40   |
| ZDT3               | IGD / HV / Pareto | IGD 1.4–2.0；HV 1.1–2.3；Pareto 20–40   |
| DTLZ2 (2 obj)      | IGD / HV / Pareto | IGD 0.10–0.22；HV 0.4–1.3；Pareto 30–50 |
| 约束类（连续）     | 可行率 / 违约率   | 可行率 >= 0.9；违约率 ≈ 0                 |
| 约束类（排列/TSP） | 约束满足 / 距离   | 约束满足=1.0；距离随代数下降               |

---

## 项目定位

NSGABlack 面向“复杂、多目标、强约束、昂贵评估”的优化问题，目标是：

- 用统一求解器内核解决连续/整数/排列/矩阵/图等不同变量类型问题
- 通过偏置系统分离“算法策略”与“业务约束”，提升迁移与复用
- 通过表征流水线减少“新问题重写编码/修复”的成本
