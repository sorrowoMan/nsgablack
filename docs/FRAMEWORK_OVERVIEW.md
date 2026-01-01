# NSGABlack 框架总览（增强版）

本文档基于当前代码实现整理，覆盖核心架构、组件职责、数据流、复用机制与扩展方式。

## 1) 项目定位与目标

NSGABlack 是一个面向多目标优化的完整生态框架，核心目标是：

- 用统一的求解器内核解决不同类型问题（连续/离散/图/矩阵）
- 通过偏置系统解耦“算法策略”和“领域约束”
- 通过多智能体角色协作提升全局搜索能力
- 通过表示管线将编码/修复/变异模块化，降低新问题重写成本

## 2) 总体架构（分层视图）

1) 问题层  
   - `core/base.py`：`BlackBoxProblem` 统一接口  
   - `evaluate(x)` / `evaluate_constraints(x)` 统一入口  

2) 表示层（Representation Pipeline）  
   - `utils/representation/` 统一编码/修复/初始化/变异  
   - 直接在正确空间采样与变异，避免“随机 + 过滤”低效模式  

3) 偏置层（Bias System）  
   - 领域偏置：约束、规则、业务偏好  
   - 算法偏置：多样性、收敛、探索控制  

4) 求解层  
   - NSGA-II 主流程（选择/交叉/变异/精英保留）  
   - 多样性初始化与收敛检测  
   - 可接入代理模型与并行评估  

5) 多智能体层  
   - Explorer / Exploiter / Waiter / Advisor / Coordinator  
   - 角色偏置 + 自适应协作  

6) 工具与实验层  
   - 可视化、历史记录、实验结果导出  
   - 并行评估/内存优化  

## 2.5) 目录速览（关键入口）

- `core/`：问题定义与求解器内核  
- `solvers/`：多智能体求解器与角色策略  
- `bias/`：偏置系统与库  
- `utils/`：并行、可视化、实验、数组/表示等工具  
- `examples/`：示例问题与工作流  
- `docs/`：框架文档与概览  

## 3) 核心组件与职责（代码映射）

### 3.1 求解器内核

- `core/solver.py`  
  - NSGA-II 主流程（交叉/变异/环境选择）  
  - `DiversityAwareInitializerBlackBox`：多样性初始化  
  - `AdvancedEliteRetention`：精英保留与替换  
  - 收敛检测与多样性评估  
  - 支持表示管线接入（初始化与变异阶段）  

### 3.2 多智能体求解器

- `solvers/multi_agent.py`  
  - 角色配置与偏置配置  
  - 角色间信息交换与策略调节  
  - 支持 role-level 的表示管线复用  

### 3.3 偏置系统

- `bias/`（包含 v1/v2 接口与兼容层）  
  - `bias_v2.py`：统一管理器  
  - `bias_library_domain.py`：领域偏置库  
  - `bias_library_algorithmic.py`：算法偏置库  
  - 支持硬约束/软约束、约束聚合与权重控制  

### 3.4 表示管线（本轮补全）

目录：`utils/representation/`  

- `base.py`：`RepresentationPipeline`  
- `continuous.py`：连续变量  
- `integer.py`：整数向量  
- `permutation.py`：排列/TSP  
- `binary.py`：二进制  
- `graph.py`：图边向量  
- `matrix.py`：矩阵结构  

兼容入口：`utils/representation_plugins.py`  

## 4) 关键数据流（以 NSGA-II 为例）

```
初始化 -> (表示管线初始化) -> 评估 -> 偏置修正 -> 选择
   -> 交叉 -> 变异 -> (表示管线变异/修复) -> 评估 -> 精英保留
```

关键点：

- 表示管线在“初始化”和“变异”阶段生效  
- 偏置系统在“评估”阶段介入（可作为硬/软约束）  
- 多智能体在“群体层面”重复以上流程并做交流融合  

## 4.5) 评价与约束处理的建议边界

- 约束落地方式：偏置系统给出惩罚/修正信号  
- 编码落地方式：表示管线直接生成合法或近合法解  
- 二者组合可兼顾效率与稳定性，避免“随机后过滤”的低效  

## 5) 多智能体协同机制（代码级细节）

角色及特性（见 `solvers/multi_agent.py`）：

- Explorer：高探索率 / 高变异 / 低选择压力  
- Exploiter：高选择压力 / 高交叉 / 低变异  
- Waiter：观察与跟随 / 维持多样性  
- Advisor：统计/ML/Bayesian 提示  
- Coordinator：动态调节比例与策略  

支持能力：

- 角色级偏置配置  
- 角色级表示管线配置  
- 动态策略调整与通信间隔控制  

## 6) 表示管线：完整类型清单（本次补全）

### 连续（`continuous.py`）

- `UniformInitializer`
- `GaussianMutation`
- `ClipRepair`

### 整数向量（`integer.py`）

- `IntegerInitializer`
- `IntegerMutation`
- `IntegerRepair`

### 排列/TSP（`permutation.py`）

- Random Keys：`RandomKeyInitializer` / `RandomKeyMutation`  
- 解码器：`RandomKeyPermutationDecoder`  
- 排列变异：`PermutationSwapMutation` / `PermutationInversionMutation`  
- 2-opt：`TwoOptMutation`  
- 交叉：`OrderCrossover` / `PMXCrossover`

### 二进制（`binary.py`）

- `BinaryInitializer` / `BitFlipMutation`  
- `BinaryCapacityRepair`（容量或预算约束）  

### 图结构（`graph.py`）

- `GraphEdgeInitializer` / `GraphEdgeMutation`  
- `GraphConnectivityRepair`（连通性修复）  
- `GraphDegreeRepair`（度约束修复）  

### 矩阵结构（`matrix.py`）

- `IntegerMatrixInitializer` / `IntegerMatrixMutation`  
- `MatrixRowColSumRepair`（行列和修复）  
- `MatrixSparsityRepair`（稀疏修复）  
- `MatrixBlockSumRepair`（块和修复）  

## 6.5) 表示管线的复用模式

- 单智能体：统一的管线用于初始化/变异/修复  
- 多智能体：按角色/子群配置不同管线，形成策略互补  
- 管线复合：在“初始化/变异/修复”阶段组合不同模块  

## 7) 偏置系统与表示管线的职责边界

推荐原则：

- 表示管线负责“生成合法或近合法解”  
- 偏置系统负责“约束惩罚与搜索引导”  

好处：

- 减少无效解比例，提高搜索效率  
- 约束逻辑清晰集中，不侵入算法内核  

## 8) 工程与实验支持

主要特性（以代码实现为准）：

- 多样性初始化与历史记忆  
- 精英保留/替换策略  
- 收敛检测与噪声判断  
- 并行评估接口（`utils/parallel_evaluator.py`）  
- 可视化支持（`utils/visualization.py`）  
- 实验导出（`utils/experiment.py`）  

## 8.5) 典型复用工作流（面向新问题）

1) 定义问题与评价函数：继承 `BlackBoxProblem`  
2) 选择表示管线：按变量类型（连续/整数/排列/矩阵/图）  
3) 选择偏置：领域约束 + 算法偏置  
4) 选择求解器：单智能体或多智能体  
5) 运行实验并导出记录  

## 9) 代表性工作流（示例路径）

### TSP（随机键编码）

- 示例：`examples/tsp_representation_pipeline_demo.py`  
- 表示管线：随机键初始化/变异 + argsort 解码  

### 偏置系统

- 示例：`examples/tsp_simple_demo.py`  
- 领域偏置与算法偏置组合  

### 多智能体优化

- 入口：`solvers/multi_agent.py`  
- 支持 role 配置与动态调整  

## 10) 为什么适合作为研究展示

该框架体现：

- 清晰的抽象层次（问题/表示/偏置/求解）  
- 可复用与可扩展性设计（插件式）  
- 面向复杂约束与离散问题的解决能力  
- 多智能体协同与智能指导机制  
- 可落地的“编码/修复/初始化/变异”模块化范式  
- 适用于离散组合优化与约束优化的统一思路  

---

版本：v1.1  
作者：独立完成  
状态：持续迭代  
