# 生产排程问题的解题思路（对照真实代码）

下面不是“讲算法”，而是**按实际代码结构讲清楚：为什么这样设计、每一步解决什么问题**。  
本文严格对照了以下文件：

- `examples/cases/production_scheduling/working_integrated_optimizer.py`
- `examples/cases/production_scheduling/problem/production_problem.py`
- `examples/cases/production_scheduling/pipeline/schedule_pipeline.py`
- `examples/cases/production_scheduling/bias/production_bias.py`
- `examples/cases/production_scheduling/refactor_data.py`

---

## 1) 问题分析（为什么这样建模）

这个排程问题的核心难点不是“算法”，而是**结构**：
- 约束高度耦合（机器、物料、天数相互牵制）  
- 可行域非常窄（合法排程远少于非法排程）  
- 多目标天然冲突（高产量 vs 平滑度 vs 设备利用）  

因此分析结论是：
1) **先锁硬约束**，否则任何搜索都在无效空间里浪费  
2) **软目标必须显式化**，否则结果不可解释  
3) **策略应可替换**，避免把业务结构绑死在算法里  

这直接导出框架拆解顺序：  
Pipeline → Bias → Adapter → Plugin。

---

## 2) 先把问题讲清楚（从数据和变量出发）

**业务规模**（来自代码默认配置，可被数据文件覆盖）：
- 机种数量：22  
- 计划周期：30 天  
- 物料种类：156（你可以在数据文件中覆盖）  

**核心数据**（见 `refactor_data.py`）：
- BOM 矩阵 `bom_matrix[machine, material]`  
  - 读取 `BOM.csv / BOM.xlsx` 或历史文件  
- 供给矩阵 `supply_matrix[material, day]`  
  - 读取 `SUPPLY.xlsx` 或历史供给文件  
- 设备权重 `machine_weights`（用于初始化中的偏好）

**决策变量**：  
排程矩阵 `schedule[machine, day]`，每个元素是**当天该机种的产量**。  
在代码里它被展平成长度 `machines * days` 的向量（见 `ProductionSchedulingProblem`）。

**关键约束**（见 `ProductionConstraints` + `evaluate_constraints`）：  
- 每天启用机器数量 ∈ `[min_machines_per_day, max_machines_per_day]`  
- 单台机器产量 ∈ `[min_production_per_machine, max_production_per_machine]`  
- 物料短缺惩罚（消耗不能超过供给）  

**目标函数**（见 `evaluate`）：  
该问题不是单一“最小成本”，而是**多目标**组合：
- 最大化总产量（代码里是 `-total_production`）  
- 生产波动（方差/平滑度）  
- 机器满载偏差  
- 连续性/空转惩罚  
- 可选的“惩罚目标”（`penalty_objective`）  

**建议插图**：  
`[图1：问题规模 + 数据结构（BOM/供给/排程矩阵）]`

---

## 2) 为什么先做 Pipeline（硬约束优先）

在排程问题里，“不合法的解”没有任何价值。  
因此先做**硬约束落地**，把可行性锁进 Pipeline。

对应代码：`pipeline/schedule_pipeline.py`

### 设计逻辑（对应代码里的做法）
- **初始化**  
  - `ProductionScheduleInitializer`：随机生成合法排程  
  - `SupplyAwareInitializer`：基于供给/BOM/权重做更“现实”的初始化  
- **变异 / 修复**  
  - 通过局部扰动，再修复越界或冲突  

**为什么这样设计？**  
因为需要保证：  
> “无论后面算法怎么换，解的可行性始终成立。”

这就是 Pipeline 的价值：**把硬约束从算法里剥离掉**。

**建议插图**：  
`[图2：Pipeline（初始化/变异/修复）结构示意]`

---

## 3) Bias：把软偏好“显式化”

偏好不是硬约束，但会决定“什么样的解更好”。  
在代码里用 Bias 把它显式化（`bias/production_bias.py`）：

### 具体偏好信号（代码中的 Bias）
- 物料短缺惩罚  
- 过度启用机器惩罚  
- 设备使用率奖励  
- 日产量波动惩罚  
- 覆盖率奖励  

**为什么要显式化？**  
因为可以明确地说：  
> “在这些偏好设定下得到结果。”  
而不是把偏好藏在算法里，导致结果不可解释。

**建议插图**：  
`[图3：Bias 列表 + 权重示意]`

---

## 4) Adapter：策略内核只负责搜索

Adapter 的职责很纯粹：**在可行解空间里移动**。  
入口脚本里用了“可组合策略”，这就是框架优势：

- 你可以选 NSGA-II 作为稳定基线  
- 也可以加入 SA / VNS 做局部补充  
- 但 Pipeline 和 Bias 不变  

对应代码：`working_integrated_optimizer.py`

**为什么这样设计？**  
因为策略可以替换，但问题结构不应该被污染。  
这让算法的变化变得“低风险、可验证”。

**建议插图**：  
`[图4：Adapter 只负责 propose/update 的示意]`

---

## 5) Plugin：让实验可复现、可审计

真实项目里，结果的可信度比“跑通”更重要。  
入口脚本里挂了这些能力：

- `BenchmarkHarnessPlugin`：统一实验输出口径  
- `ModuleReportPlugin`：记录偏置贡献  
- `ParetoArchivePlugin`：保留帕累托解集  
- `ProfilerPlugin`：性能剖析  

对应代码：`working_integrated_optimizer.py`

**为什么这样设计？**  
因为工程能力和算法逻辑必须分离，  
这样才能保证：**复现、审计、对比**都可靠。

**建议插图**：  
`[图5：输出（CSV/summary/模块报告）示意]`

---

## 6) 最终结构与框架优势

**Problem（业务语义）**  
→ **Pipeline（硬约束合法性）**  
→ **Bias（软偏好显式化）**  
→ **Adapter（搜索策略可替换）**  
→ **Plugins（实验可复现/可审计）**  

**框架优势在这里体现**：
- 算法可替换，但问题结构稳定  
- 偏好可解释，而不是隐式“魔法调参”  
- 实验结果可复现，不是“跑通就算”  

**补充说明（避免混淆）**：  
`utils` 是运行时基础设施层，不是插件层。  
`context` 作为系统状态总线放在 `utils` 中，是为了强调它的**通用性与基础设施属性**。  
Plugin/Adapter 会在运行时**读写 context**，但生命周期仍属于组件本身。  

**建议插图**：  
`[图6：完整 wiring 图]`

---

## 7) 复现入口

入口脚本：  
- `examples/cases/production_scheduling/working_integrated_optimizer.py`

建议流程：
1) 只开 BenchmarkHarness，跑 baseline  
2) 加 Bias，看偏好贡献变化  
3) 切换 Adapter，观察策略差异  
4) 用 Run Inspector 做结构审查
