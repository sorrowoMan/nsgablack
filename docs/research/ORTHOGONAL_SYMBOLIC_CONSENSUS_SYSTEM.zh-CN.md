# 正交符号共识系统

当前 `nsgablack -> mlblack` 正交符号共识体系的中文总览。

状态：

- 当前可工作的系统总结
- 已纳入最近一轮机制刷新
- 作为架构、使用方式、产品面和机制讨论的共享参考

---

## 1. 目标

这套系统不是“跑一次符号回归”这么简单。

它是一套分层系统，用来完成：

1. 发现相对正交的符号 basis 项
2. 在小预算下做 basis 组装
3. 在一个 cycle 内重复多次运行
4. 从多次运行中提取稳定 core basis
5. 用 locked core 重新执行 refinement
6. 把整条过程写入 runtime run/artifact surface
7. 在产品化 experiment dashboard 中审查整条演化过程

更直白一点，这套体系的目标是把下面这整条链路正式化：

1. basis 发现
2. basis-set 结构搜索
3. 小预算符号组装
4. 多次运行共识
5. 锁核 refinement
6. 真值恢复评估
7. 可观察的 runtime catalog 与 dashboard surface

---

## 2. 系统范围

当前范围包括：

- `mlblack` 的 symbolic orthogonal trainer 与 basis 搜索引擎
- `mlblack` 的 basis consensus 与 locked-core 选择逻辑
- `nsgablack` 的外层 orchestration scaffold
- `nsgablack` 的 runtime surface tracker
- `nsgablack` 的 experiment catalog / dashboard
- 已知关系 benchmark suite 的正式脚手架

这说明它已经不只是一个算法模块。

它同时具有四张“脸”：

1. 算法面
2. 编排面
3. 合同面
4. 产品面

---

## 3. 分层架构

这套栈有两个常用视角。

### 3.1 框架级视角

`nsgablack`

- 负责外层编排
- 负责外层搜索预算
- 负责 runtime surface 持久化
- 负责 experiment UI / catalog 产品面

`mlblack`

- 负责真实的符号建模逻辑
- 负责 basis 搜索、symbolic assembly 与 truth recovery
- 负责从 consensus 到 locked-core 的符号工作流

### 3.2 运行级视角

`L1`：外层 `nsgablack` solver

- 选择 orchestration / search-budget 参数
- 把整套 mlblack symbolic orchestration 当成一次内层评估

`L2`：consensus cycle orchestration

- 连续运行多次 unlocked symbolic attempt
- 计算 consensus table
- 产出 locked-core seed genome

`L3`：stage 级执行

- `unlocked_batch`
- `consensus`
- `locked_core_refinement`

真正的符号建模运行主要发生在 `L3` 内的 `mlblack` 侧。

---

## 4. 关键文件地图

### 4.1 `mlblack`

Basis 搜索引擎：

- `C:\Users\hp\Desktop\mlblack\core\symbolic\orthogonal_basis_search.py`

Consensus 与 locked core：

- `C:\Users\hp\Desktop\mlblack\core\symbolic\basis_consensus.py`

Trainer：

- `C:\Users\hp\Desktop\mlblack\core\trainers\symbolic_orthogonal_trainer.py`

### 4.2 `nsgablack`

Backend 桥接：

- `C:\Users\hp\Desktop\nsgablack\plugins\solver_backends\mlblack_symbolic_consensus_backend.py`

外层脚手架入口：

- `C:\Users\hp\Desktop\nsgablack\examples\cases\mlblack_symbolic_consensus_scaffold\run_project.py`

Benchmark suite runner：

- `C:\Users\hp\Desktop\nsgablack\examples\cases\mlblack_symbolic_consensus_scaffold\run_benchmark_suite.py`

Outer problem：

- `C:\Users\hp\Desktop\nsgablack\examples\cases\mlblack_symbolic_consensus_scaffold\problem\outer_problem.py`

Runtime surface tracker：

- `C:\Users\hp\Desktop\nsgablack\plugins\storage\runtime_surface_tracker.py`

Experiment dashboard：

- `C:\Users\hp\Desktop\nsgablack\experiment\dashboard.py`

Experiment CLI：

- `C:\Users\hp\Desktop\nsgablack\experiment\cli.py`

统一 UI 壳：

- `C:\Users\hp\Desktop\nsgablack\ui\dashboard.py`

---

## 5. 正式合同层

runtime / 产品面围绕四层正式记录组织：

1. `SurfaceRecord`
2. `AssemblyRecord`
3. `RunRecord`
4. `ArtifactRecord`

相关协议文档：

- `docs/project/RUN_SURFACE_CONTRACT.md`
- `docs/project/RUN_ARTIFACT_SURFACE_PROTOCOL.md`

四层含义：

- `SurfaceRecord`：这是哪个标准脚手架 surface
- `AssemblyRecord`：真实挂载的栈是什么
- `RunRecord`：一次具体执行实例
- `ArtifactRecord`：一个具体输出对象

这几层不是抽象文书，而是 experiment UI 能回答下面问题的根基：

1. 跑的是哪个 benchmark / scaffold surface
2. 用的是哪条 symbolic mechanism path
3. 这是哪个 cycle / stage / run
4. 产出了哪些 artifact 和 summary

---

## 6. 端到端执行流

标准路径如下：

1. `nsgablack` 外层 solver 提出一个 orchestration candidate
2. 把 candidate 解码为 benchmark、search-budget、consensus 参数
3. 内层 runtime 委托给 `MlblackSymbolicConsensusBackend.solve(...)`
4. backend 构建 benchmark data bundle
5. backend 运行 unlocked symbolic runs
6. backend 构建 core basis table
7. backend 选择 locked-core seed genome
8. backend 运行 locked-core refinement symbolic runs
9. backend 汇总 leaderboard、cycle report、stage report 和 basis evolution
10. runtime surface tracker 持久化全部 surface
11. dashboard 读取这些持久化 surface

从产品角度看：

- 系统输出的不只是一个 best expression
- 系统输出的是一段结构化的演化历史

---

## 7. 机制总览

当前 symbolic 机制有五个关键层次。

### 7.1 第一层：候选筛选

第一层筛选已经不再只是 marginal target correlation。

当前筛选协议：

- `target corr`
- `residual gain`
- `semantic novelty`
- `consensus prior`

含义：

- `target corr`：这个候选和目标是否相关
- `residual gain`：在当前 baseline fit 之后，这个项是否还能解释残差
- `semantic novelty`：它在候选池里是否语义不冗余
- `consensus prior`：它是否贴近此前已经出现的稳定 core row

对外字段：

- `screening_protocol = target_corr+residual_gain+semantic_novelty+consensus_prior`

### 7.2 第二层：外层 basis-set 结构搜索

外层搜索已经不再是从固定候选列表里做简单贪心组装。

现在它是 beam 风格的 basis-set structure search。

重要特征：

- 多个 seed state
- 分支扩展
- beam frontier pruning
- 相关性控制
- 特征复用控制
- 语义重复控制
- piecewise / gate bonus 支持
- locked-core 阶段的 seed locking

对外字段：

- `outer_search_protocol = beam_basis_set_structure_search`

外层扩展时会重点考虑：

- pairwise absolute correlation
- feature overlap penalty
- family diversity bonus
- semantic family bonus
- 相对当前残差的 residual correlation
- marginal `R2` gain
- piecewise gate bonus

### 7.3 第三层：组级外层目标

选中的 basis-set 会被一个联合组目标打分。

当前组级逻辑显式考虑：

- mean screen score
- orthogonality score
- residual complementarity
- semantic uniqueness
- pairwise correlation penalty
- feature overlap penalty

所以外层已经在扮演真正的 symbolic structure search objective，而不是一个简单排序器。

### 7.4 第四层：内层小预算符号组装

当外层 basis set 选定后，内层不再只是 ridge-only readout。

它会在选定 basis 空间上运行一次小预算 symbolic assembly。

目的：

- 保持内层 symbolic composition 成本可控
- 允许在选定 basis 空间内部继续做 symbolic refinement
- 保留真正的第二阶段符号回归，而不是只做线性读出

相关跟踪字段：

- `inner_symbolic_search`
- `assembler_budget`

### 7.5 第五层：多次运行共识与锁核

系统会先在一个 cycle 内收集多次 unlocked run。

然后在不同等价模式下构造 consensus table：

- `strict`
- `phase`
- `family`

接着选择 locked-core seed genome，再执行 locked refinement。

正是这一层把“单次符号运行”升级成了“多次运行的符号系统”。

---

## 8. 锁核机制

当前 locked-core selection 已经不是 family-only。

它使用一个联合分数，来源于：

- `support_rate`
- `exact_stability`
- `support_weight_rate`

当前公式：

- `joint_core_score = 0.50 * support_rate + 0.30 * exact_stability + 0.20 * support_weight_rate`

含义：

- `support_rate`：跨多少次运行出现
- `exact_stability`：在选中的 family / phase 组内，是否有一个 exact form 持续占主导
- `support_weight_rate`：加权支持率，通常受运行质量或外层目标影响

当前重要输出包括：

- `exact_stability`
- `multi_run_core_frequency`
- `joint_core_score`
- `representative_exact_support_rate`
- `selection_source`

Backfill 模式：

- 当前系统支持 `weighted_rank` backfill
- 当纯 consensus 产出的 seed term 太少时，这个模式会补位

---

## 9. 真值恢复评估

系统不只报告 RMSE。

它会从多个层次跟踪 truth recovery：

- `exact_basis_hit_score`
- `exact_term_recovery_score`
- `phase_equivalent_term_recovery_score`
- `family_level_term_recovery_score`

含义：

- `basis_hit`：真实 basis 项是否出现
- `term_recovery`：即使 exact basis 不同，最终表达式是否恢复了该真值项
- `phase-equivalent`：给周期项或相位等价项一个更合理的等价类
- `family-level`：从更高层机制 family 粒度看是否恢复了正确方向

这对 symbolic system 特别重要，因为：

- 完全相同的表达式匹配往往过严
- family-level recovery 可以在语法不同的情况下揭示机制方向是否正确

---

## 10. 基准族

当前 known-relation benchmark family 包括：

- `ohm_like`
- `ideal_gas_like`
- `arrhenius_gate_like`
- `periodic_gate_like`
- `redundant_proxy_control`

它们分别针对不同失败模式：

- ratio 结构
- 指数机制
- piecewise / gate 行为
- 周期等价
- 冗余代理混淆

---

## 11. 产品面

这套系统已经有正式的产品化 experiment surface。

### 11.1 Runtime 表面

当前 experiment runtime surface 直接暴露：

- `runtime_run_surface`
- `runtime_artifact_surface`

dashboard 直接读取这两张 surface。

### 11.2 派生产品字段

最近已经做成可直接筛选的字段包括：

- `screening_protocol`
- `outer_search_protocol`
- `joint_core_score_min`
- `consensus_prior_row_count`
- `selected_core_row_count`

这些字段不是装饰性 metadata。

它们让 UI 可以直接问：

- 哪些 run 使用了新的四段 screening protocol
- 哪些 run 使用了新的 outer basis-set search
- 哪些 run 的 locked-core confidence 高于某个阈值

### 11.3 Dashboard 行为

experiment dashboard 当前支持：

- run catalog view
- artifact catalog view
- deep-link / URL state
- 选中行恢复
- 可点击结果表格
- contract detail view
- payload detail view
- cycle / stage / basis-evolution 审查

---

## 12. Runtime Surface 语义

同一个 DB 里会混合多种 run 粒度。

### 12.1 Outer Solver Summary

典型形态：

- scaffold 级 summary
- best run / leaderboard / comparison

### 12.2 Consensus Cycle Surface

典型形态：

- 单个 cycle summary
- core selection
- cycle 级 comparison

### 12.3 Stage Surface

典型 stage key：

- `unlocked_batch`
- `consensus`
- `locked_core_refinement`

### 12.4 Flow Surface

典型形态：

- 一次具体 symbolic run
- 含 direct symbolic search summary
- 最适合审真实 basis row 和 truth recovery

---

## 13. 标准使用方式

### 13.1 跑一个正式脚手架

```powershell
python examples\cases\mlblack_symbolic_consensus_scaffold\run_project.py `
  --benchmark-key ohm_like `
  --generations 3 `
  --pop-size 6 `
  --vanilla-runs 3 `
  --locked-runs 2
```

### 13.2 跑一组 benchmark suite

```powershell
python examples\cases\mlblack_symbolic_consensus_scaffold\run_benchmark_suite.py `
  --suite-id my_suite `
  --benchmarks ohm_like arrhenius_gate_like redundant_proxy_control `
  --consensus-cycles 2 `
  --unlocked-runs-per-cycle 2 `
  --locked-runs-per-cycle 1 `
  --generations 2 `
  --pop-size 2 `
  --batch-size 4
```

### 13.3 打开 Experiment UI

```powershell
python -m nsgablack experiment ui --db "C:\path\to\runtime_surface.sqlite3"
```

### 13.4 打开统一首页

```powershell
python -m nsgablack ui
```

### 13.5 用 CLI 筛选运行面

```powershell
python -m nsgablack experiment list-runs `
  --db "C:\path\to\runtime_surface.sqlite3" `
  --screening-protocol "target_corr+residual_gain+semantic_novelty+consensus_prior" `
  --outer-search-protocol "beam_basis_set_structure_search" `
  --joint-core-score-min 0.5
```

---

## 14. 典型输出文件

一个 suite 通常会产出：

- `orchestrator_benchmark_suite_summary.json`
- `orchestrator_benchmark_suite_table.csv`
- `runtime_surface.sqlite3`
- 每个 benchmark 的 `summary.json`
- 每个 benchmark 的 `orchestration_summary.json`
- `cycle_reports.json`
- `stage_reports.json`
- `core_basis_evolution.json`
- `locked_core_selection.json`

最近的 truth-frequency 分析还会产出：

- `truth_frequency_report.json`
- `truth_frequency_report.csv`

---

## 15. 当前基准效果概览

### 15.1 `ohm_like`

观察到的模式：

- locked-core 可以改善 RMSE
- 最好的 exact recovery 仍可能停留在 orthogonal run
- 这说明 locked refinement 已经影响到有用结构，但“拟合最优”和“真值恢复最优”并不总是一致

### 15.2 `redundant_proxy_control`

观察到的模式：

- locked-core 当前是有帮助的
- consensus prior 可以抬升一部分 unlocked 阶段漏掉的真值项
- 最近的大一点的 run 里，`drift_bias` 在 locked-core 下的出现频率提升了

解释：

- consensus / locked-core 对“冗余代理混淆”确实在起作用

### 15.3 `arrhenius_gate_like`

观察到的模式：

- consensus prior 和 locked-core 变得稳定了
- 但它们可能稳定的是错误的 proxy family
- 最近这轮更大预算的运行并没有抬高真机制项频率

解释：

- 当前问题不只是预算大小
- 它更像是机制选择问题
- 系统锁定的是稳定 proxy basis，而不是期望的 Arrhenius 风格机制 basis

---

## 16. 当前优势

当前这套栈已经把几件难事做对了：

1. 坚持走正式脚手架路径，而不是 ad hoc demo glue
2. multi-run consensus 已正式化
3. locked core 已正式化
4. truth recovery 是多层次的，不是只看 RMSE
5. runtime surface 是可持久化、可查询的
6. experiment dashboard 支持 deep-link 和点击交互
7. 机制协议字段已经进入产品筛选面

这已经是一套很严肃的系统基础设施。

---

## 17. 当前弱点

当前主要弱点：

1. 一些 benchmark 仍会收敛到稳定 proxy，而不是真实机制 basis
2. `arrhenius_gate_like` 仍是最清晰的失败案例
3. locked-core 的质量取决于 unlocked 阶段先暴露了什么
4. 当近似等价结构占优势时，exact basis recovery 仍然困难
5. 系统仍需要更强的 mechanism-family-aware outer objective

---

## 18. 这套体系现在本质上是什么

最合适的描述是：

- 一套嵌套式 symbolic search system
- 以 orthogonal-basis-first 的结构发现为起点
- 带有 budgeted symbolic assembly
- 带有 multi-run consensus
- 带有 locked-core refinement
- 带有正式 runtime surface
- 带有产品级 experiment inspection

所以它已经不再只是：

- 一个 trainer
- 一次 symbolic regression
- 一个 benchmark script

它已经是一整套完整的 symbolic experimentation stack。

---

## 19. 当前最建议的下一步

如果目标是机制忠实度，而不只是稳定拟合，那么最值当的下一步是：

1. 把 outer objective 进一步朝 mechanism-family truth candidate 倾斜，尤其是 `arrhenius_gate_like`
2. 让 `exp_ratio` / `gate` 这类 family 在面对稳定单特征 proxy 时更容易胜出
3. 保留当前 consensus / locked-core 机制，但提升它所允许稳定下来的结构质量

简化一句话：

- consensus machinery 已经不再是主要缺失项
- 下一道前沿是更强的 mechanism-aware structure preference

---

## 20. 近期相关产物

最近一轮较大 benchmark suite：

- `examples/cases/mlblack_symbolic_consensus_scaffold/runs/benchmark_suite/orchestrator_arrhenius_redundant_mech_refresh_20260505/`

其中重要文件：

- `orchestrator_benchmark_suite_summary.json`
- `runtime_surface.sqlite3`
- `truth_frequency_report.json`
- `truth_frequency_report.csv`

这些文件目前是审查下面几件事的最好参考：

- 真实机制行为
- consensus prior 行为
- locked-core 对 truth frequency 的影响
- dashboard-ready 的 runtime surface

---

## 21. 两个正式机制护栏

当前这套系统应该把下面两件事视为正式机制护栏，而不是 trainer 里的零散启发式。

### 21.1 等价表达式处理机制

它负责：

- 在经验等价 / 残差等价 / 语义等价之间建立等价类
- 在局部等价家族内部选择代表表达
- 当多个 symbolic 形式本质上指向同一个机制坐标时，降低伪新颖性

对外字段：

- `equivalence_expression_protocol`
- `equivalence_expression_mode`
- `equivalence_class_scope`

### 21.2 干扰特征处理机制

它负责：

- 抑制 proxy-like 干扰特征
- 惩罚在高重叠特征来源上的浅层非线性伪装
- 为后续 cross-explanatory rejection 和 invariance audit 预留正式协议位点

对外字段：

- `interference_feature_protocol`
- `interference_feature_mode`
- `cross_explanatory_rejection_mode`
- `trivial_nonlinearity_penalty_mode`
- `environment_invariance_audit_mode`

当前状态：

- 协议字段以及 artifact/runtime surface 投影已正式化
- 真正的硬拒绝逻辑目前仍是 heuristic-first，还不是完整的因果/干预级实现
