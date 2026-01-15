# 供应链嵌套优化中的代理流程指南

本指南面向“外层供应计划 + 内层生产优化”的嵌套问题，说明如何在框架中搭建、训练、更新和使用代理模型，从而降低真实评估成本并保持优化稳定性。

## 1. 适用场景与目标

适用场景：
- 外层变量规模大（如 22x31 的整数矩阵），真实评估需要调用内层生产优化。
- 评估昂贵、预算受限，且需要多轮迭代搜索。
- 希望把代理模型作为“加速组件”，而不是替代问题建模。

核心目标：
- 减少真实评估次数，提升整体迭代速度。
- 在代理误差不可避免的前提下，保持搜索稳定性。
- 可与偏置系统、多智能体系统协同使用。

## 2. 输入清单

必须具备：
- `problem.evaluate(x)`：真实评估函数（可调用内层生产优化）。
- `bounds/representation`：编码模块给出的变量类型、维度、边界。
- 评估预算：总真实评估次数、单次时间、可用并行资源。

建议补充：
- `evaluate_constraints(x)`：约束信息用于筛选/打分。
- 目标噪声描述：随机波动或仿真误差程度。
- 评估缓存策略：记录 `X_real/y_real` 以便训练与复用。

## 3. 代理角色选择（关键决策）

你可以用同一个代理模型承担不同角色：

1) 预筛选  
代理先评估一批候选，只对 TopK 做真实评估。  
优点：显著减少真实评估次数。  
风险：误杀潜在好解。

2) 评分偏置  
代理只影响评分/注入，不直接替代真实评估。  
优点：风险最低，适合早期样本少。  
风险：加速效果有限。

3) 替代评估  
对低不确定性样本直接用代理值替代真实评估。  
优点：速度提升最大。  
风险：误导收敛风险最高。

4) 组合（推荐）  
预筛选 + 评分偏置 + 部分替代评估。  
优点：速度与稳定性兼顾，适合嵌套优化。

## 4. 数据流总览

```
真实评估 -> 评估缓存(X_real/y_real)
          -> 训练集构建(过滤/去重/特征)
          -> 代理训练与质量检测
          -> 参与预筛选/评分偏置/替代评估
          -> 新真实评估回流更新
```

## 5. 训练集构建策略

数据来源优先级（建议）：
1) 已真实评估的历史数据（最可信）。
2) 当前迭代生成的候选 + 真实评估结果。
3) 档案库中的可行解（用于扩充多样性）。

筛选建议：
- 只保留可行解或低违约解作为主训练集。
- 使用分位数过滤（例如取前 60% 的目标值）。
- 高维离散问题强烈建议做“特征压缩”：
  - 行列汇总、容量余量、库存缺口等统计特征。
  - 低秩参数化或结构化编码输出。

## 6. 模型选择规则

建议将“编码模块元信息 + 评估预算 + 噪声”组合决定模型：

| 情况 | 推荐模型 | 理由 |
| --- | --- | --- |
| 低维连续(<=15)、样本少 | GP | 样本效率高，适合昂贵评估 |
| 中高维连续(>30) | RBF / RF | 训练更快，鲁棒性更好 |
| 高维整数/混合 | RF / Ensemble | 对离散与噪声更稳 |
| 类型未知或不稳定 | Ensemble | 稳健但成本更高 |

供应链矩阵类问题通常属于“高维整数/混合”，默认 RF 或 Ensemble。

## 7. 质量检测与信任机制

代理必须可自我监控，否则容易误导搜索：
- 质量指标：R2、RMSE、排序相关性(如 Spearman)。
- 信任阈值：低于阈值时降低代理权重或回退统计策略。
- 保留“真实评估比例”：即便代理很准，也保留 10%-30% 的真实评估作为校准。

## 8. 迭代流程（面向供应链嵌套问题）

1) 定义编码与边界（供应计划矩阵 -> 编码向量）。  
2) 初始采样并真实评估，建立 `X_real/y_real`。  
3) 训练代理模型，完成质量检测。  
4) 每一代执行：
   - 生成候选（NSGA-II 或多智能体搜索）。  
   - 预筛选：代理过滤大量候选，仅保留 TopK 真实评估。  
   - 评分偏置：Advisor 使用代理评分打分并注入候选。  
   - 替代评估：对低不确定性样本直接用代理值。  
   - 更新缓存与代理模型。  
5) 记录代理质量与真实评估占比，必要时调整策略。

### 8.1 伪代码（组合版）

```text
Inputs:
  problem.evaluate(x)       # 内层生产优化的真实评估
  representation.encode()   # 编码模块: 变量类型/维度/边界/特征
  surrogate_config          # 模型类型/更新频率/信任阈值
  role_config               # 预筛选/评分偏置/替代评估/组合
  budget_config             # 真实评估预算/TopK比例/真实评估比例

Initialize:
  X_real, y_real = []
  pop = initialize_population()
  for x in pop.initial_samples:
      y = evaluate_real(problem, x)
      cache(X_real, y_real, x, y)
  surrogate = train_surrogate(X_real, y_real)
  quality = evaluate_quality(surrogate, X_real, y_real)
  trust = quality >= trust_threshold

Loop for generation = 1..max_generations:
  candidates = generate_candidates(pop)

  if use_prefilter:
      scores = surrogate.predict(candidates)
      candidates = top_k(candidates, scores, topk_ratio)

  evaluated = []
  for x in candidates:
      if use_surrogate_eval and trust and low_uncertainty(x):
          y = surrogate.predict(x)
          tag = "surrogate"
      else:
          y = evaluate_real(problem, x)
          cache(X_real, y_real, x, y)
          tag = "real"
      evaluated.append((x, y, tag))

  if use_score_bias:
      advisor_scores = surrogate.score(evaluated)
      inject_advisor_candidates(pop, advisor_scores)

  update_population(pop, evaluated)
  update_archives(pop)

  if generation % update_interval == 0:
      surrogate = train_surrogate(X_real, y_real)
      quality = evaluate_quality(surrogate, X_real, y_real)
      trust = quality >= trust_threshold

  if real_eval_budget_reached():
      break

Output:
  best_solutions, pareto_front, surrogate_quality_log
```

## 9. 参数建议（经验值）

| 参数 | 建议区间 | 说明 |
| --- | --- | --- |
| initial_samples | 30-200 | 高维问题需更大起步样本 |
| update_interval | 3-10 代 | 过频易过拟合，过稀易滞后 |
| real_eval_ratio | 10%-30% | 真实评估占比，保证稳定 |
| topk_ratio | 10%-20% | 预筛选保留比例 |
| trust_threshold | 0.6-0.8 | 低于阈值就降权或回退 |

## 10. 与框架的对接点

可直接复用的模块：
- `solvers/surrogate.py`：代理训练与质量检测流程。
- `core/solver.py`：偏置启用与目标修正入口。
- `multi_agent/components/advisor.py`：Advisor 评分偏置入口。
- `bias/specialized/bayesian.py`：可作为 Advisor 的偏置策略补充。

## 11. 常见风险与规避

- 代理误差主导搜索：提高真实评估比例，启用质量阈值回退。  
- 高维整数难拟合：优先 RF/Ensemble + 特征压缩。  
- 可行解比例过低：筛选时保留“低违约解”，避免代理只学不可行区域。  

## 12. 快速检查清单

- 是否定义了可复用的编码/解码模块？  
- 是否建立了真实评估缓存（X_real/y_real）？  
- 是否明确代理角色（预筛选/评分偏置/替代评估/组合）？  
- 是否有质量检测和回退机制？  
- 是否保留一定比例真实评估用于校准？  

ok我们现在怎么训练这个模型呢，假设生产计划算法已经有了，是一个就是库内能搭建的nsga，或者是多智能体，接下来怎么做
把“内层生产优化”封进外层 evaluate(x)
跑初始样本得到 X_real/y_real
训练代理 + 质量检测
进入外层迭代：代理参与预筛选/评分/替代
每 N 代或新增 M 条真实样本重训


