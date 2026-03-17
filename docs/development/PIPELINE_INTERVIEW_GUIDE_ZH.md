# `nsgablack` Pipeline（Representation）面试复习文档

> 面向面试复习 / 表示层理解 / 候选解管线落地。
>
> 本文基于仓库源码整理，重点参考：
>
> - `representation/base.py`
> - `representation/__init__.py`
> - `core/blank_solver.py`（encode/decode/init/mutate 接口）
> - `core/composable_solver.py`（候选修复接入点）

---

## 1. 先记住：Pipeline 在这个框架里是什么

`RepresentationPipeline` 是候选解唯一的“形态处理总线”。

它统一管理：

1. `initializer`：怎么生成候选
2. `mutator`：怎么扰动候选
3. `repair`：怎么修复可行性
4. `encoder`：怎么做编码/解码
5. `crossover`：怎么做重组（可选）

一句话：**Adapter 决策“搜哪里”，Pipeline 决策“候选长什么样、怎么被修好”。**

---

## 2. 核心类与工程护栏（`representation/base.py`）

### 2.1 核心类

- `RepresentationPipeline`
- `ParallelRepair`
- `ContinuousRepresentation`
- `IntegerRepresentation`
- `PermutationRepresentation`
- `MixedRepresentation`

### 2.2 工程护栏开关（高频）

- `transactional`：失败回滚
- `protect_input`：输入防污染
- `copy_context`：上下文副本隔离
- `threadsafe`：锁保护并发
- `validate_constraints` / `max_init_attempts`：初始化可行性重试

---

## 3. Pipeline 调用链（口述版）

典型路径：

1. `init(problem, context)` 生成候选
2. `mutate(x, context)` 扰动
3. `repair.repair(x, context)` 修复
4. `encode/decode` 在 solver 侧按需调用

与 solver 关系：

- `SolverBase.init_candidate()` / `mutate_candidate()` 走 pipeline
- `ComposableSolver.step()` 在评估前对候选统一 `repair`

---

## 4. 组件逐项介绍（按 `representation/__init__.py`）

### 4.1 Continuous 组件

| 组件                        | 作用一句话                | 适用场景     |
| --------------------------- | ------------------------- | ------------ |
| `UniformInitializer`      | 连续空间均匀初始化        | 连续优化基线 |
| `GaussianMutation`        | 高斯扰动变异              | 局部探索     |
| `ContextGaussianMutation` | 受 context 控制的高斯扰动 | 分阶段调节   |
| `PolynomialMutation`      | 多项式变异                | 演化算法常用 |
| `SBXCrossover`            | 模拟二进制交叉            | NSGA/GA      |
| `ClipRepair`              | 边界裁剪修复              | 连续边界约束 |
| `ProjectionRepair`        | 投影式修复                | 几何约束     |

### 4.2 Integer 组件

| 组件                   | 作用一句话     | 适用场景   |
| ---------------------- | -------------- | ---------- |
| `IntegerInitializer` | 整数空间初始化 | 离散决策   |
| `IntegerMutation`    | 整数扰动       | 整数优化   |
| `IntegerRepair`      | 整数/边界修复  | 离散可行性 |

### 4.3 Permutation 组件

| 组件                             | 作用一句话          | 适用场景      |
| -------------------------------- | ------------------- | ------------- |
| `PermutationInitializer`       | 排列初始化          | 排序/调度     |
| `PermutationRepair`            | 排列可行性修复      | 组合约束      |
| `PermutationFixRepair`         | 强修复缺失/重复元素 | 排列纠错      |
| `PermutationSwapMutation`      | 交换变异            | 局部邻域搜索  |
| `PermutationInversionMutation` | 逆序变异            | 排列优化      |
| `TwoOptMutation`               | 2-opt 邻域          | 路径优化      |
| `OrderCrossover`               | 顺序交叉            | 排列 GA       |
| `PMXCrossover`                 | 部分映射交叉        | 排列 GA       |
| `RandomKeyInitializer`         | 随机键编码初始化    | 连续-排列桥接 |
| `RandomKeyMutation`            | 随机键变异          | 随机键法      |
| `RandomKeyPermutationDecoder`  | 随机键解码为排列    | 编码解码桥接  |

### 4.4 Binary / Graph / Matrix 组件

| 组件                         | 作用一句话     | 适用场景      |
| ---------------------------- | -------------- | ------------- |
| `BinaryInitializer`        | 二值初始化     | 0-1 优化      |
| `BinaryRepair`             | 二值可行修复   | 容量/逻辑约束 |
| `BitFlipMutation`          | 比特翻转变异   | 二值搜索      |
| `BinaryCapacityRepair`     | 容量型二值修复 | 选址/背包     |
| `GraphEdgeInitializer`     | 图边初始化     | 图结构优化    |
| `GraphEdgeMutation`        | 图边扰动       | 图搜索        |
| `GraphConnectivityRepair`  | 连通性修复     | 图可行性      |
| `GraphDegreeRepair`        | 度约束修复     | 图约束        |
| `IntegerMatrixInitializer` | 整数矩阵初始化 | 矩阵型决策    |
| `IntegerMatrixMutation`    | 矩阵扰动       | 矩阵优化      |
| `MatrixRowColSumRepair`    | 行列和约束修复 | 运输/分配     |
| `MatrixSparsityRepair`     | 稀疏性修复     | 稀疏结构      |
| `MatrixBlockSumRepair`     | 分块和约束修复 | 分区约束      |

### 4.5 辅助组件

| 组件                     | 作用一句话                                         |
| ------------------------ | -------------------------------------------------- |
| `BoundConstraint`      | 通用边界约束描述                                   |
| `ContextSelectMutator` | 根据 context 动态选择变异器                        |
| `DynamicRepair`        | 动态修复策略包装                                   |
| `ParallelRepair`       | repair 批处理并行包装（thread/process + fallback） |

---

## 5.  Pipeline 的意义

- Adapter 不应该知道具体编码细节
- 同一算法要复用到连续/排列/图/矩阵多表示
- 约束修复需要统一可治理，不应散落在算法内部

一句话：

> Pipeline 是“搜索语义”和“候选形态”之间的隔离层，是框架可扩展性的关键。

---

## 6. 面试追问模板（Pipeline）

### Q1：为什么 repair 不放在 adapter 里？

A：repair 是表示层职责，放 adapter 会导致算法与问题编码强耦合，破坏可复用性。

### Q2：Pipeline 怎么保证并发安全？

A：有 `threadsafe` 锁、`protect_input` 防污染、`transactional` 回滚和 `ParallelRepair` 的失败回退。

### Q3：Pipeline 和 snapshot 有关系吗？

A：间接关系。Pipeline 决定候选形态，snapshot 负责大对象持久与引用；两者通过 solver 评估链路衔接。

---

## 7. 30 秒口述模板（Pipeline）

> `nsgablack` 的 Pipeline 把 initializer、mutator、repair、encoder/crossover 统一进表示层，保证算法层不关心候选编码细节。我们通过 `RepresentationPipeline` 的工程护栏（事务、并发、上下文隔离）让候选处理可复现、可治理，再由 solver 在评估前统一调用 repair，这样同一 adapter 能稳定复用到连续、离散、排列、图和矩阵等多种问题形态。

---

## 8. 一页速记（只背这些）

- Pipeline = 候选形态总线
- Adapter 管策略，Pipeline 管编码/变异/修复
- repair 是硬约束最后防线
- `ParallelRepair` 支持并行与回退
- 护栏：`transactional/protect_input/copy_context/threadsafe`
- 多表示统一是框架扩展性的核心
