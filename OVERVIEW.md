# OVERVIEW

## 项目定位

NSGABlack 是多目标优化工程框架，目标是把“算法实验”提升为**可分层、可治理、可复现**的工程系统。

---

## 四层正交架构

- **Solver**：生命周期与控制平面  
- **Adapter**：算法策略与搜索逻辑  
- **Representation**：候选解表示与算子管线  
- **Plugin**：工程能力与运行期扩展  

---

## 运行数据流（标准一代）

`adapter.propose -> representation -> evaluate_population -> adapter.update -> plugin hooks`

---

## 评估链路（L4）

- 支持评估短路与代理评估  
- 同时支持 `individual` 与 `population` 两条路径  
- 近似评估默认关闭，可通过 `EvaluationMediatorConfig.allow_approximate=True` 开启  

---

## Context / Snapshot 分层

- **Context**：小字段与引用  
- **Snapshot**：大对象（population/objectives/violations）  

---

## Catalog 双口径

- `default`：完整口径（含 example/doc）  
- `framework-core`：主干口径（排除 example/doc）  

架构审计与主干统计使用 `framework-core`。

---

## 适用与边界

适合：  
多目标优化、混合策略编排、复杂约束、可复现工程流程

不适合：  
只需单一算法的轻量脚本、一次性实验

