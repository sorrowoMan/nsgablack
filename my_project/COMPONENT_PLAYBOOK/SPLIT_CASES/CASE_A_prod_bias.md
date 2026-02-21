# Case A（真实排产）- Bias 逐行批注

来源：`examples/cases/production_scheduling/refactor_bias.py`

```python
def build_production_bias_module(problem, weights: Optional[Dict[str, float]] = None) -> BiasModule:  # 偏置模块装配入口
    module = BiasModule()  # 创建 bias 容器
    weights = weights or {}  # 权重字典兜底

    shortage_weight = weights.get("shortage_penalty", 0.02)  # 缺料惩罚权重
    excess_weight = weights.get("excess_machine_penalty", 0.01)  # 超机器惩罚权重
    utilization_weight = weights.get("utilization_reward", 0.02)  # 利用率奖励权重
    smooth_weight = weights.get("smoothness_penalty", 0.01)  # 平滑惩罚权重
    variance_weight = weights.get("variance_penalty", 0.0)  # 方差惩罚权重
    coverage_weight = weights.get("coverage_reward", 0.02)  # 覆盖率奖励权重

    if shortage_weight > 0:  # 如果启用缺料偏置
        module.add(  # 注册一个 CallableBias
            CallableBias(  # 通用可调用偏置
                name="material_shortage",  # 偏置名
                func=_PenaltyFromConstraints(CONSTRAINT_INDEX["material_shortage"], key="material_shortage"),  # 直接读约束分量
                weight=float(shortage_weight),  # 权重
                mode="penalty",  # 惩罚模式
            )
        )

    if excess_weight > 0:  # 如果启用超机器偏置
        module.add(
            CallableBias(
                name="excess_machines",  # 名称
                func=_PenaltyFromConstraints(CONSTRAINT_INDEX["excess_machines"], key="excess_machines"),  # 读约束索引1
                weight=float(excess_weight),  # 权重
                mode="penalty",  # 惩罚
            )
        )

    if utilization_weight > 0:  # 启用利用率奖励
        module.add(
            CallableBias(
                name="utilization_reward",  # 名称
                func=_UtilizationReward(  # 奖励函数：按日活跃机种占比计算
                    machines=int(problem.machines),  # 机种数
                    days=int(problem.days),  # 天数
                    max_machines_per_day=int(problem.constraints.max_machines_per_day),  # 目标机台上限
                ),
                weight=float(utilization_weight),  # 权重
                mode="reward",  # 奖励模式
            )
        )

    if smooth_weight > 0:  # 启用平滑惩罚
        module.add(
            CallableBias(
                name="smoothness_penalty",  # 名称
                func=_SmoothnessPenalty(machines=int(problem.machines), days=int(problem.days)),  # 计算日间变化率
                weight=float(smooth_weight),  # 权重
                mode="penalty",  # 惩罚模式
            )
        )

    if variance_weight > 0:  # 启用方差惩罚
        module.add(
            CallableBias(
                name="variance_penalty",  # 名称
                func=_VariancePenalty(machines=int(problem.machines), days=int(problem.days)),  # 计算 std/mean
                weight=float(variance_weight),  # 权重
                mode="penalty",  # 惩罚模式
            )
        )

    if coverage_weight > 0:  # 启用覆盖率奖励
        module.add(
            CallableBias(
                name="coverage_reward",  # 名称
                func=_CoverageReward(machines=int(problem.machines), days=int(problem.days), feasible_mask=feasible_mask),  # 奖励“更多机种被激活”
                weight=float(coverage_weight),  # 权重
                mode="reward",  # 奖励模式
            )
        )

    return module  # 返回偏置模块
```

## 重点理解
- 这里 bias 是“偏好层”，不是算法主循环。
- 大部分偏置直接消费 `evaluate_constraints` 的结果（结构清晰、可解释）。
- 权重本质是业务偏好强度，不是问题本体参数。
