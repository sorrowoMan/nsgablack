# 05. mlblack 符号学习、机制组件与结构发现对齐

本页只说明 mlblack 语义层里的符号学习组件如何落位。它不定义新的顶层编排系统；项目顺序、资源授权和嵌套调度由共享 substrate 处理。

## 覆盖范围

- `core/symbolic/*`
- `core/symbolic/feature_space/*`
- `core/mechanisms/*`
- `core/orthogonal_source/*`
- `core/symbolic/benchmark/*`

## 符号学习主干

| 代码对象 | 社区概念 | 当前职责 |
| --- | --- | --- |
| `symbolic_dsl.py` | expression DSL / program grammar | 定义表达式空间与可序列化结构 |
| `symbolic_gradient.py` | symbolic differentiation | 为机制诊断与候选修正提供梯度信号 |
| `gradient_parser.py` | gradient signal parser | 从残差或梯度中抽取结构线索 |
| `gradient_correction.py` | gradient-based correction | 在连续拟合与结构搜索之间提供修正算子 |
| `structure_optimizer.py` | symbolic structure optimizer | 管理候选结构的局部搜索或改写 |
| `symbolic_structure_search.py` | program search | 作为 ML 语义组件暴露结构候选生成能力 |
| `truth_contracts.py` | benchmark contract | 描述真实结构、恢复指标与评估口径 |
| `structure_contract.py` | structure schema | 让结构可记录、比较、复现 |

## Trainer / Head / Artifact

| 代码对象 | 社区概念 | 当前职责 |
| --- | --- | --- |
| `SymbolicStagewiseSurrogateTrainer` | stagewise symbolic regression | 训练一个分阶段符号模型 |
| `SymbolicOrthogonalTrainer` | orthogonal basis symbolic regression | 发现稳定 basis 并拟合 |
| `SymbolicOrthogonalIntervalTrainer` | interval symbolic regression | 输出区间预测语义 |
| `stage_head_protocol.py` | output head protocol | 区分函数结构与输出头语义 |
| `trainer_state_io.py` | trainer state persistence | 保存可恢复状态，artifact 另行记录 |

Trainer 是 Case 内部的 ML 语义组件。它可以被 Project 作为外层 Case 运行，也可以被另一个 Case 作为内层 evaluator 调用。

## Feature Space

| 子系统 | 社区概念 | 当前职责 |
| --- | --- | --- |
| candidate pool | dictionary / basis candidate pool | 管理可选 primitive 与候选函数 |
| generation grammar | grammar-based generation | 按语法生成候选结构 |
| primitive registry | operator registry | 注册基础算子 |
| feature bundle | representation bundle | 组合特征或表达式来源 |
| objective policy | scoring policy | 定义 ML 语义内的评分口径 |
| evaluation cache key | memoization identity | 管理可复用评估结果 |
| fold report | fold-level report | 输出交叉验证或分割级证据 |
| regime router | mixture-of-experts gate | 管理条件分支或 regime |

## Mechanism 与 Orthogonal Source

Mechanism 是可组合语义组件，不是新的运行入口。

| 代码对象 | 社区概念 | 当前职责 |
| --- | --- | --- |
| `core/mechanisms/protocols.py` | mechanism protocol | 定义可插拔机制接口 |
| `family_bindings.py` | semantic binding | 声明组件与语义预设的关系 |
| `runtime.py` | mechanism execution helper | 在 Case 内部运行机制组件 |
| `search_mechanism_contract.py` | search mechanism contract | 标明哪些自由度适合交给外层搜索 |
| `core/orthogonal_source/layer.py` | source governance | 管理多来源特征或信息源 |

## 与 nsgablack 对接

mlblack 通过标准 Case surface 暴露：

- candidate payload
- evaluation result payload
- artifact references
- audit report
- local resource request

nsgablack 不读取 mlblack 内部 Trainer 细节；它只消费标准 payload、objectives、violations、artifact refs 与运行审计。
