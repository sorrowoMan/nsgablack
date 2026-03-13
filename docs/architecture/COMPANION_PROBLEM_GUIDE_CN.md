# 伴随问题（等值面模式）说明

本文说明如何在**不改变问题域**的前提下，通过 Solver 的控制面切换
“纵向优化”与“横向等值面探索”。

## 1. 定义

- 主问题：优化目标 `f(x)`。
- 伴随问题：仍在同一问题域内，但采用“等值面附近接受”作为新准则。

伴随问题**不会改变**：
- `problem` 定义
- `pipeline`（编码/修复）
- `bias` 逻辑
- adapters（候选生成器）

它只改变：Solver 控制面状态与接受/筛选规则。

## 2. 价值与边界

用途：
- 后期横向探索，跨越盆地
- 提升 Pareto 多样性
- 在不增加组件的情况下完成跳簇

边界：
- 不是数学证明机制
- 主要用于连续或可微问题

## 3. 状态模型（控制面字段）

必需字段：
- `search_mode`：`"vertical"` 或 `"lateral"`
- `levelset_targets`：目标等值面列表（目标向量）
- `levelset_eps`：容差（标量或逐维）
- `levelset_budget`：每个目标的尝试预算
- `levelset_policy`：目标选择策略（`best`/`frontier`/`round_robin`）
- `levelset_accept`：接受规则（`l2`/`linf`/`bandwidth`/`weighted`）
- `levelset_outcome`：成功/失败统计

可选字段：
- `levelset_anchor_key`：对应 Pareto 点的标识
- `levelset_phase`：阶段编号

建议写入 context 的字段：
- `context["search_mode"]`
- `context["levelset_target"]`
- `context["levelset_eps"]`
- `context["levelset_budget_used"]`
- `context["levelset_success_count"]`
- `context["levelset_fail_count"]`

## 4. 伴随问题构建

对于每个 Pareto 解 `x`：
- 计算 `b = f(x)`
- 记录 `b` 为等值面目标

多目标接受规则：
- `l2`：`||f(x') - b|| <= eps`
- `linf`：`max_i |f_i(x') - b_i| <= eps`
- `bandwidth`：`f_i(x') in [b_i - eps_i, b_i + eps_i]`
- `weighted`：`sum_i w_i * |f_i(x') - b_i| <= eps`

单目标接受规则：
- `|f(x') - b| <= eps`

## 5. 调度策略

示例：
1. `t < t_switch`：纵向模式
2. `t >= t_switch`：按预算混合
3. 每个 epoch：
   - `p%` 预算纵向
   - `1-p%` 预算横向

目标选择策略：
- `frontier`：优先最新前沿点
- `round_robin`：轮询
- `best`：按标量化排序

## 6. 接受与处理

当 `search_mode = "lateral"`：
1. adapters 生成候选
2. solver 评估 `f(x')`
3. 满足容差则接受
4. 接受后：
   - 加入 Pareto 候选池
   - 更新多样性统计
5. 否则记录失败

如果预算内无法命中：
- 标记为 `exhausted`
- 丢弃或提高 `eps` 再试

## 7. 失败模式与护栏

常见问题：
- 修复后等值面漂移
- `eps` 过小导致无法命中
- 可行域碎片导致难以横向移动

护栏：
- 连续失败时放宽 `eps`
- 每个目标有限重试
- 修复后再对比 `f(x')` 与 `b`

## 8. 最小伪代码

```python
def step():
    if search_mode == "vertical":
        candidates = propose()
        accept_vertical(candidates)
        return

    target = pick_levelset_target()
    for _ in range(levelset_budget):
        x = propose_one()
        fx = evaluate(x)
        if levelset_accept(fx, target, eps):
            accept_candidate(x, fx)
            record_success(target)
            break
    else:
        record_failure(target)
```

## 9. 建议默认值

- `t_switch`: `0.4 * max_steps`
- `levelset_eps`: 初期较大，逐步收紧
- `levelset_budget`: 每目标 3-10 次尝试
- `levelset_policy`: `frontier` 或 `round_robin`
- `levelset_accept`: 多目标优先 `linf`
