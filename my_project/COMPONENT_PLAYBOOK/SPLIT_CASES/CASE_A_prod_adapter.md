# Case A（真实排产）- Adapter 逐行批注

来源：`examples/cases/production_scheduling/working_integrated_optimizer.py`

真实排产是“多策略协同”，核心是 `MultiStrategyControllerAdapter`，由 explorer/exploiter 两个角色组成。

```python
roles = []  # 角色列表，后续交给 MultiStrategyControllerAdapter

roles.append(  # explorer 角色
    RoleSpec(  # 角色配置
        name="explorer",  # 角色名
        adapter=lambda uid: MOEADAdapter(  # 每个单元用一个 MOEA/D adapter
            MOEADConfig(  # MOEA/D 参数
                pop_size=moead_pop,  # 子问题数量
                neighborhood_size=moead_neighbor,  # 邻域大小
                delta=moead_delta,  # 邻域采样概率
                nr=moead_nr,  # 每次最大替换数
                random_seed=(args.seed + uid),  # 不同单元用不同种子
            )
        ),
        n_units=2,  # explorer 单元个数
        weight=1.0,  # 角色权重
    )
)

roles.append(  # exploiter 角色
    RoleSpec(
        name="exploiter",  # 角色名
        adapter=lambda uid: VNSAdapter(  # 每个单元用 VNS adapter
            VNSConfig(  # VNS 参数
                batch_size=max(8, args.vns_batch_size // 2),  # 每步候选数
                k_max=args.vns_k_max,  # 邻域层级上限
                base_sigma=args.vns_base_sigma,  # 基础 sigma
                random_seed=(args.seed + 1000 + uid),  # 单元独立种子
            )
        ),
        n_units=2,  # exploiter 单元个数
        weight=1.0,  # 角色权重
    )
)

cfg = MultiStrategyConfig(  # 控制器全局配置
    total_batch_size=total_batch,  # 每步总候选数
    objective_aggregation="sum",  # 目标聚合策略
    adapt_weights=True,  # 开启角色权重自适应
    stagnation_window=max(5, int(args.adapt_interval)),  # 停滞窗口
    phase_schedule=(("explore", max(5, int(args.generations // 3))), ("exploit", -1)),  # 阶段计划
    phase_roles={"explore": ["explorer"], "exploit": ["exploiter"]},  # 每阶段允许的角色
)

controller = MultiStrategyControllerAdapter(roles=roles, config=cfg)  # 构建控制器 adapter

solver = ComposableSolver(  # 组合求解器
    problem=problem,  # 问题
    adapter=controller,  # 过程控制核心
    representation_pipeline=pipeline,  # 管线
    bias_module=bias_module,  # 偏置
)
```

## 重点理解
- 这里 adapter 是“算法过程的一等公民”。
- explorer（MOEA/D）负责全局探索，exploiter（VNS）负责局部精修。
- controller 统一调度角色和阶段，而不是把逻辑散在 solver 主循环里。
