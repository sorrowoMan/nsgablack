# Case C（稳健优化）- Adapter 逐行批注

目标：把“多保真决策流程”放在 adapter，而不是 bias/plugin。

```python
class RobustFidelityAdapter(AlgorithmAdapter):  # 稳健多保真 adapter
    name = "robust_fidelity_adapter"  # 名称

    context_requires = ("population", "objectives", "generation")  # 依赖字段
    context_provides = ("task", "strategy", "strategy_id")  # 提供任务提示字段
    context_mutates = ("task",)  # 更新 task
    context_cache = ()  # 不缓存
    context_notes = ("Choose low/high fidelity evaluation policy by stage and uncertainty.",)  # 说明

    def __init__(self, switch_gen: int = 30):  # 参数：多少代后偏向高保真
        super().__init__(name=self.name)  # 父类初始化
        self.switch_gen = int(switch_gen)  # 阶段切换代数

    def propose(self, solver, context):  # 生成候选并给出评估策略建议
        pop = np.asarray(context["population"], dtype=float)  # 当前种群
        objs = np.asarray(context["objectives"], dtype=float)  # 当前目标
        gen = int(context.get("generation", 0))  # 当前代
        best_idx = int(np.argmin(objs[:, 0]))  # 按 obj0 找最好
        base = pop[best_idx]  # 基准解
        rng = self.create_local_rng(solver)  # 局部 RNG
        cand = base + rng.normal(0.0, 0.1, size=base.shape)  # 局部扰动
        fidelity = "high" if gen >= self.switch_gen else "low"  # 阶段策略
        self._last_task = {"eval_fidelity": fidelity, "reason": "stage_switch"}  # 保存任务提示
        return [cand]  # 返回候选列表

    def update(self, solver, context):  # 回写策略信息到 context
        _ = solver  # 当前示例不直接读 solver
        _ = context  # 当前示例不使用 context
        return {  # 返回 context 增量
            "task": dict(getattr(self, "_last_task", {"eval_fidelity": "low", "reason": "default"})),  # 任务字段
            "strategy": "robust_fidelity",  # 策略名
            "strategy_id": "rf-01",  # 策略实例 id
        }
```

## 重点
- “走低保真还是高保真”属于流程决策，放 adapter 最合适。
- plugin 负责记录，bias 负责偏好，adapter 负责调度。
