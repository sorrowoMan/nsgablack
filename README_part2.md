- 通过代理与多智能体增强搜索效率与资源分配能力

---

## 核心亮点

- 偏置系统：算法偏置 + 领域偏置，支持硬/软约束与奖励惩罚
- 表征流水线：编码/修复/初始化/变异/交叉全链路模块化
- 多智能体协作：Explorer/Exploiter/Waiter/Advisor/Coordinator 角色分工
- 代理辅助：预筛选/评分偏置/替代评估统一接口
- 并行与内存优化：并行评估接口、内存优化工具、历史记录
- 丰富示例与验证脚本：覆盖 TSP、图结构、矩阵、混合变量等

---

## 小巧思与设计精妙点

- 约束外置：偏置可返回约束违约度，约束逻辑不侵入求解器
- 表征先行：在正确空间内初始化/变异，避免“随机过滤”的低效
- 算法偏置化：将强算法抽象为偏置层，可挂接到 NSGA-II 底座复用
- 角色与偏置解耦：角色只负责分工，策略通过偏置组合实现
- 代理统一接口：预筛选/评分偏置/替代评估三种方式统一配置
- 代理控制偏置：阶段切换、预算调度、不确定性驱动可偏置化
- 精英替换与历史记忆：兼顾稳定性与跳出局部最优

---

## 功能矩阵

| 模块                            | 功能                       | 典型用途               |
| ------------------------------- | -------------------------- | ---------------------- |
| `core/`                       | 黑箱问题接口、NSGA-II 内核 | 任意优化问题的基础求解 |
| `bias/`                       | 算法/领域/代理偏置         | 规则、偏好、策略引导   |
| `utils/representation/`       | 连续/整数/排列/矩阵/图表征 | 编码、修复、变异复用   |
| `multi_agent/`                | 多智能体协作               | 角色分工、资源分配     |
| `surrogate/`                  | 代理训练与评估             | 昂贵黑箱加速           |
| `solvers/`                    | 多种求解器入口             | NSGA-II、MC、代理集成  |
| `utils/parallel_evaluator.py` | 并行评估                   | 提升评估吞吐           |
| `tools/`                      | 工具脚本                   | 索引/文档/验证         |

---

## 对外展示入口

建议对外展示只使用精简入口，详见：

- `docs/user_guide/external_api_navigation.md`

推荐导入方式：

```python
from nsgablack import (
    BlackBoxProblem,
    BlackBoxSolverNSGAII,
    BiasModule,
    ParallelEvaluator,
    SurrogateAssistedNSGAII,
    SurrogateUnifiedNSGAII,
    MonteCarloOptimizer,
)
from nsgablack.solvers import MultiAgentBlackBoxSolver
```

---

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 最小多目标示例

```python
from core.solver import BlackBoxSolverNSGAII
from core.problems import ZDT1BlackBox

problem = ZDT1BlackBox(dimension=10)
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 100
solver.max_generations = 50
result = solver.run()

print(f"Pareto 解数量: {len(result['pareto_solutions'])}")
```

### 加入偏置（约束业务规则）

```python
from bias.bias import BiasModule

def constraint_penalty(x, constraints, context):
    violation = max(0.0, x[0] + x[1] - 1.0)
    return {"penalty": violation, "constraint": violation}

bias = BiasModule()
bias.add_penalty(constraint_penalty, weight=10.0, name="sum_limit")

solver.bias_module = bias
solver.enable_bias = True
```

---

## 核心能力详解

### 1) 偏置系统（bias）

偏置是本项目的核心设计，用于统一处理：

- 算法策略（多样性/探索/收敛等）
- 领域规则（业务约束/偏好/规则）
- 代理控制（阶段切换/不确定性预算）

偏置支持返回约束违约度，直接参与排序与筛选。

### 2) 表征流水线（representation）

编码/修复/初始化/变异/交叉被拆分为可组合模块：

- 连续、整数、排列、矩阵、图结构均有对应管线
- 单智能体与多智能体共享同一套表示体系
- 新问题只需更换管线，无需重写求解器

### 3) 代理模型（surrogate）

为昂贵评估提供加速手段：

- 训练与评估工具齐全（采样/训练/检测/复训）
- 统一代理接口支持三种模式：预筛选/评分偏置/替代评估
- 代理控制偏置可实现阶段策略与不确定性预算

### 4) 多智能体协作（multi-agent）

角色分工与协作机制：

- Explorer/Exploiter/Waiter/Advisor/Coordinator
- Advisor 支持统计/贝叶斯/ML 生成候选
- Coordinator 根据质量与轮次进行角色调度

### 5) 工程与并行支持

- 并行评估接口：提升昂贵目标的吞吐
- 内存优化工具：适配大规模问题
- 实验记录与可视化：便于评估与复现

---

## 典型工作流

1. 定义问题（`BlackBoxProblem`）
2. 选择表征管线（连续/整数/排列/矩阵/图）
3. 选择偏置（算法偏置 + 业务偏置）
4. 选择求解器（单机 / 多智能体 / 代理辅助）
5. 运行与验证（示例脚本/基准）

---

## 项目结构速览

```
core/                 # 黑箱问题与 NSGA-II 内核
bias/                 # 偏置系统（算法/领域/代理）
utils/representation/ # 表征流水线
multi_agent/          # 多智能体系统
surrogate/            # 代理训练/评估/策略
solvers/              # 求解器入口集合
examples/             # 示例与演示
docs/                 # 文档与说明
tools/                # 工具脚本
```

---

## 验证与测试

运行整体冒烟验证：

```bash
python examples/validation_smoke_suite.py
```

---

## 选择追踪（可选，性能开销）

选择追踪用于**解释“为何保留/淘汰个体”**，适合高精度调参、偏置精炼和诊断实验。
它会带来**I/O 与序列化开销**，不建议在长跑或大规模默认开启。

推荐用法：

- 小规模/短跑实验
- `stride>1`（隔代记录）
- `mode="summary"` / `mode="stats"` 或设置 `max_records`
- `flush_interval>1`（缓冲写入，降低 I/O）
- 在有强算力或需要深度诊断时开启

启用示例：

```python
# 单机 NSGA-II
solver.enable_selection_tracing(
    path="reports/selection_trace/selection_trace_ZDT1.jsonl",
    mode="stats",
    max_records=50,
    stride=5,
    flush_interval=5
)

# 多智能体
multi_solver.enable_selection_tracing(
    path="reports/selection_trace/selection_trace_multi_agent_ZDT1.jsonl",
    mode="stats",
    max_records=50,
    stride=5,
    flush_interval=5
)
```

---

## 偏置贡献与消融（Bias attribution & ablation）

- 看贡献：在选择追踪输出中，关注各 Bias 的分量（penalty/score/constraint 等）；可统计“被选个体的 Bias 分量均值/Top-K”。
- 做消融：保持同一 Pipeline/问题，仅切换 Bias on/off，或分组 profile（如 `algo_bias`, `domain_bias`, `surrogate_bias`）。
- 读 trace：
  - `mode="summary"`：代级聚合，适合快速看哪类 Bias 起主导作用。
  - `mode="stats"`：统计均值/方差/极值，便于看分布。
  - `stride`/`max_records` 控制采样，减少 I/O。
- 建议流程：

1) 仅开启核心 Bias，跑短程；2) 逐个打开新 Bias，看指标变化；3) 保留有效 Bias，记录配置。

最小示例（摘取核心片段，可嵌入任意脚本）：

```python
from bias.bias import BiasModule

def penalty_sum_limit(x, constraints, context):
        violation = max(0.0, x[0] + x[1] - 1.0)
        return {"penalty": violation, "constraint": violation}

bias = BiasModule()
bias.add_penalty(penalty_sum_limit, weight=10.0, name="sum_limit")

solver.bias_module = bias
solver.enable_bias = True

solver.enable_selection_tracing(
        path="reports/selection_trace/demo.jsonl",
        mode="summary",
        max_records=50,
        stride=5,
        flush_interval=5,
)
```

---

## 如何新增：问题类 / Pipeline / Bias（5 步）

1) 新问题类：在 `core/problems.py`（或相邻文件）新增 `YourProblem(BlackBoxProblem)`，实现目标、约束、维度与变量范围。
2) 选/建 Pipeline：
   - 若已有表征可复用，直接在 solver 中引用（如连续/整数/排列）。
   - 若需新表征，在 `utils/representation/` 下新增编码/修复/初始化/变异/交叉模块，并在相关 `__init__.py` 暴露入口。
3) 写 Bias：在 `bias/`（或子目录）写一个函数/类，返回 penalty/constraint/score 等字典；用 `BiasModule.add_*` 注册。
4) Glue：在你的脚本或 solver 配置中，绑定 Pipeline 与 Bias（`solver.pipeline = ...`; `solver.bias_module = bias`）。
5) 验证：用小规模跑 `examples/validation_smoke_suite.py` 或自制短程脚本，观察 Pareto 数、可行率、IGD/HV，再按需做消融。

提示：保持单一改动（只换问题、或只换 Pipeline、或只加 Bias），便于定位贡献与回归。

更具体的落点（便于定位文件）：

- 问题类：`core/problems.py`（或子模块）；如需特殊数据，放在 `data/`。
- Pipeline：`utils/representation/<type>/` 下新增模块，更新同级 `__init__.py` 暴露；必要时在 `core/solver.py` 里引用。
- Bias：`bias/` 顶层或对应子目录（`algorithmic/`, `domain/`, `surrogate/` 等），并在 `bias/__init__.py` 暴露。
- 示例脚本：在 `examples/` 添加最小可跑脚本，便于回归与文档引用。

---

## 文档导航

- 框架总览：`docs/FRAMEWORK_OVERVIEW.md`
- 详细介绍：`docs/PROJECT_DETAILED_OVERVIEW.md`
- 关键质疑回应：`docs/FRAMEWORK_DESIGN_QA.md`
- 代理流程：`docs/user_guide/surrogate_workflow.md`
- 代理速查：`docs/user_guide/surrogate_cheatsheet.md`
- 偏置教程：`docs/user_guide/bias_baby_guide.md`
- 对外展示入口：`docs/user_guide/external_api_navigation.md`

---

## 性能与环境说明

- Python 版本：3.8+
- 可选 Numba：用于内存优化；未安装时会自动降级
- 并行评估：`ParallelEvaluator` 基于多进程，Windows 需在 `if __name__ == "__main__":` 中启动
- 昂贵评估：建议先用代理做预筛选/评分，再切回真实评估
- 日志控制：可关闭内存优化与进度日志，降低输出噪音

常见疑问速答（FAQ）

- 参数太多从哪里下手？先用默认 profile，逐个开启 Bias 组做消融；记录 IGD/HV/可行率的变化。
- > 2 目标如何评估？优先 IGD、Pareto 数、可行率；HV 目前仅推荐 2 目标。
  >
- 偏置会拖慢吗？开销主要是少量函数调用和 I/O；相比昂贵评估成本可忽略，建议保留接口。
- Windows 并行报错？确保入口放在 `if __name__ == "__main__":`，并避免在全局创建大对象。

---

## 常见质疑速览（Q&A 精选）

- 核心问题与创新：面向“多目标+强约束+黑箱”场景，用“偏置 + 表征 + 稳定求解底座”解耦策略与业务；可迁移、可复用、可解释。
- 与 NSGA-II/MOEA/D 差异：NSGA-II 只是执行内核，策略/约束/代理都以偏置挂载；也可将 MOEA/D 风格启发式做成偏置组合。
- 偏置是否主观：偏置是显式可关的策略，贡献可查可消融；保留无偏路径与权重上限，降低偏差风险。
- 约束为何外置：减少耦合、便于迁移；问题本体只评估，约束与偏好通过偏置统一处理。
- 表征与偏置分工：能结构性保证的放表征/修复，复杂不等式与偏好放偏置；先“最小可行表征”，再按需增强。
- 多智能体定位：是多角色协同优化（非 MARL）；角色分工 + 偏置组合，按预算/质量调度。
- 代理模型使用：昂贵评估时做预筛/评分/替代评估；用置信门控与定期回退真实评估避免漂移。
- 指标与公平性：IGD/HV + Pareto 数/可行率/时间；固定预算与种子，结果落盘可复现；HV 仅建议 2 目标。
- 单点性能 vs 复用：精调专用算法可偏置化，沉淀为“偏置资产”可复用；定位在迁移与可控性而非单点最优。
- 什么时候不用偏置：问题简单、实时性极高、需精确最优时可直接裸跑或用解析方法；接口仍在，开销可忽略。
- 偏置冲突与组合：硬约束优先；保留无偏路径；可用线性加权/字典序/门控触发，避免单一公式锁死搜索。
- 收敛性与理论边界：偏置有界且不消灭基底搜索概率时可保持弱收敛；工程上用“无偏路径+权重上限”稳态运行。
- 过拟合业务的风险：通过跨问题迁移与消融验证；偏置透明可关，风险是显式可控的。
- 偏置强度怎么设：阶段调度（探索→收敛）、反馈调节（可行率低则加惩罚/修复）、上限约束、小规模元搜索。
- 偏置太多拖慢吗：使用门控/短路/向量化；开销相对昂贵评估可忽略，长跑可关 trace 仅留指标。
- 多智能体开销：低频/增量同步、角色预算、代表解压缩档案；必要时简化为单群体以做对照。
- 代理稳定性：置信门控 + 定期真实评估回退；数据覆盖度（LHS）+ 低频重训；可用模型集成提升稳健性。
- 适用边界：黑箱、多目标、混合变量、可接受启发式近似；不适合实时、极大规模、需精确最优的场景。
- 评估体系：IGD/HV 互补，>2 目标以 IGD/Pareto/可行率为主；报告均值+方差，固定预算与种子。
- 可重现性：统一入口脚本、固定 seed、版本记录、结果落盘（JSON/CSV/报告），并行可选确定性模式。
- 学习曲线：提供默认偏置组合与模板；保留简单模式/专家模式；先排可行率，再排偏置权重，再排算子。
- 创新与工程价值：偏置化/表征化/角色化让策略沉淀为资产，长期演进与迁移成本低；不追求单点最优而追求稳健复用。

---

## 调参路线图（实操）

- 先验分层：先保可行率，再看收敛，再看多样性；依次调约束/修复偏置 → 选择/变异偏置 → 多样性偏置。
- 三步消融：1) 只开核心 Bias，跑短程；2) 逐个打开新 Bias，看 IGD/HV/可行率变化；3) 记录有效组合为 profile。
- 权重与日程：前期提高探索/多样性权重，后期提高收敛/可行性；可按代数线性/分段衰减。
- 代理安全网：设置信心门槛，不达标回退真实评估；定期重训并清洗样本。
- 日志粒度：小规模诊断时开 selection trace 与偏置分量；长跑关 trace，只保留指标与档案。

---

## 偏置与表征协同清单

- 能被确定修复的硬约束 → 放表征/修复算子；避免在偏置里做昂贵修复。
- 结构性偏好（拓扑、排列合法性） → 表征；数值软约束/偏好 → 偏置惩罚/奖励。
- 变异/交叉应尊重表征闭包（保持可行性），偏置只调节“去哪”和“选谁”。
- 需要高可解释度时，优先用分层/字典序偏置而非简单加权。

---

## 多智能体与代理的安全使用

- 角色预算：给探索角色设上限（如评估预算百分比），避免长期拖慢。
- 同步频率：低频/增量同步档案，减少通信开销。
- 代理三模式：预筛选 < 评分偏置 < 替代评估，按风险递增选择；越靠后越需要置信门控与回退。
- 校验节奏：每 N 代用真实评估校验代理或偏置效果，必要时重置权重。

---

## 复现与报告

- 种子与版本：统一设置 random seed，记录 Python/依赖版本。
- 结果落盘：JSON/CSV + 汇总 Markdown；档案与 trace 路径保持固定前缀（如 `reports/<tag>/`）。
- 基准对比：同预算同种子跑 baseline（无偏置）与配置 A/B，报告均值与方差。
- 日志模板：指标（IGD/HV/Pareto/可行率/时间）+ 偏置权重 + 代理开启状态。

---

## 场景推荐配置（示例）

- 昂贵评估 + 强约束：表征内嵌修复 + 约束偏置（高权重）+ 代理预筛选 + 并行评估；早期高探索，后期收敛。
- 多峰/多样性优先：多样性偏置（crowding/epsilon/novelty）+ 较高变异率；保留可行性底座。
- 离散/排列问题：使用排列 Pipeline + 邻域变异；约束以修复优先，偏好放在偏置评分。
- 轻量便宜问题：可关闭代理与追踪，保留偏置接口成本极低；直接用默认 Bias profile。

---

## 许可证

MIT License
