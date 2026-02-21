# Case A（真实排产）- Pipeline 逐行批注

来源：`examples/cases/production_scheduling/refactor_pipeline.py`

```python
def build_schedule_pipeline(problem, constraints, **kwargs) -> RepresentationPipeline:  # 排产管线装配入口
    if getattr(problem, "data", None) is not None:  # 有真实 BOM/供应数据时
        initializer = SupplyAwareInitializer(  # 用供应感知初始化器
            machines=problem.machines,  # 机种数
            days=problem.days,  # 天数
            min_machines_per_day=constraints.min_machines_per_day,  # 每天最少开机台数
            max_machines_per_day=constraints.max_machines_per_day,  # 每天最多开机台数
            min_production_per_machine=constraints.min_production_per_machine,  # 单机最小产量
            max_production_per_machine=constraints.max_production_per_machine,  # 单机最大产量
            bom_matrix=problem.data.bom_matrix,  # BOM
            supply_matrix=problem.data.supply_matrix,  # 供应矩阵
            machine_weights=getattr(problem.data, "machine_weights", None),  # 机种权重
        )
    else:  # 没有业务数据时
        initializer = ProductionScheduleInitializer(...)  # 使用普通随机初始化器（兜底）

    mutator = ProductionScheduleMutation(  # 变异器
        sigma=0.5,  # 基础扰动强度
        per_gene_rate=0.05,  # 基因级变异率
        toggle_rate=0.02,  # 跳变率（随机重采样）
        max_production_per_machine=constraints.max_production_per_machine,  # 上限
    )

    base_repair = ProductionScheduleRepair(  # 基础修复器：硬约束
        machines=problem.machines,  # 机种数
        days=problem.days,  # 天数
        min_machines_per_day=constraints.min_machines_per_day,  # 最少开机
        max_machines_per_day=constraints.max_machines_per_day,  # 最多开机
        min_production_per_machine=constraints.min_production_per_machine,  # 最小产量
        max_production_per_machine=constraints.max_production_per_machine,  # 最大产量
    )

    if getattr(problem, "data", None) is not None:  # 有业务数据时继续升级修复
        repair = SupplyAwareScheduleRepair(  # 供应感知修复器（核心）
            machines=problem.machines,  # 机种数
            days=problem.days,  # 天数
            min_production_per_machine=constraints.min_production_per_machine,  # 单机最小产量
            bom_matrix=problem.data.bom_matrix,  # BOM
            supply_matrix=problem.data.supply_matrix,  # 供应
            base_repair=base_repair,  # 先做基础修复，再做供应修复
            machine_weights=getattr(problem.data, "machine_weights", None),  # 机种权重
            budget_mode=kwargs.get("budget_mode", "today"),  # 预算模式
            smooth_strength=kwargs.get("smooth_strength", 0.6),  # 平滑强度
            smooth_passes=kwargs.get("smooth_passes", 2),  # 平滑轮数
        )
    else:
        repair = base_repair  # 无业务数据时用基础修复

    return RepresentationPipeline(  # 返回标准管线对象
        initializer=initializer,  # 初始解生成器
        mutator=mutator,  # 变异器
        repair=repair,  # 修复器
        encoder=None,  # 当前不做编码映射
    )
```

## 重点理解
- 真实排产里，`repair` 是“硬约束第一责任人”。
- `SupplyAwareScheduleRepair` 的职责是把“库存可行性 + 连续性 + 覆盖率”拉回现实区间。
- `mutator` 支持 `mutation_sigma/vns_k`，是为了和 VNS adapter 的 context 协同。
