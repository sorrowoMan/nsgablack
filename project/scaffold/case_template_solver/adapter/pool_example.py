"""可选的池驱动搜索装配；在 build_solver 中显式选择，不自动启用。

需要回收闲置解时，在首次发布前配置：
    from nsgablack.core import PoolRetentionPolicy
    solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=20))
活 Unit 和待处理输入会保留；窗口外的旧发布须显式 pin 或保存可传输 checkpoint。

已有多角色装配需要子池精修时，可给 RoleSpec 增加：
    pool_task=PoolTaskSpec(select_refs, count="all", steps=5, output="refined")
其中 select_refs(control, context) 返回 SolutionRef 序列，是具名函数。
返回种群角色使用 PoolTaskSpec("refined", mode="compete", phases=("return",))。
阶段切换仍由 MultiStrategyConfig.phase_policy/phase_roles 决定。
完整可运行示例见 examples/cases/solution_pool/cases/pool_refinement。
省略 select 默认读母池；种群用 PoolTaskSpec(mode="initialize") 即按声明大小独立抽样。
指定子池必须存在。VNS 默认一个起点；count="all" 用于整批精修。
distribution 可选 independent/partition/shared；on_insufficient 可选 error/wait/available。

MOEA/D 自动生成带实例来源的方向投影子池，可直接给 VNS 角色装配：
    from nsgablack.adapters import MOEADAdapter, PoolTaskSpec, subpools
    moead = MOEADAdapter(name="adapter1", population_size=100)
    local_task = PoolTaskSpec(subpools.random(20, moead), steps=3, output="refined")
all(moead) 选择全部方向；把同一个 moead 实例装入 Router 的另一个角色。
默认 count=1 是每方向一个起点，partition 分配方向给 VNS 实例，不重复抽签。
完整装配与双目标问题见 examples/cases/solution_pool/cases/moead_refinement。

继续精修时保留明确的 VNS 实例 coarse，并将它装入上述 local 角色：
    fine_task = PoolTaskSpec(subpools.all(coarse), steps=3, output="fine")
下一层角色消费 coarse 的最终选择视图，继承原方向投影；不会再次对标量求标量。
Router 须先等待 coarse 任务完成，再调度 fine。all() 不隐含完成屏障。
视图只增引用及来源元数据；不用的聚合 output 与派生视图都需显式释放。
标准例子可用 nested_refinement=True 启用 MOEA/D→粗搜 VNS→细搜 VNS→返回。
"""
from nsgablack.adapters import (
    NSGA2Adapter, NSGA3Adapter, PoolSearchAdapter, PoolSearchSpec,
    SimulatedAnnealingAdapter,
)


def build_pool_adapter(*, producer=None, searches=None, stagnation_steps=20, recovery_steps=5):
    """取解配额与各算法容量独立；可直接替换 producer/searches 的装配。"""
    if producer is None:
        producer = SimulatedAnnealingAdapter(name="seed_sa", batch_size=7, random_seed=7)
    if searches is None:
        searches = [
            PoolSearchSpec(NSGA2Adapter(name="population_a", population_size=4, offspring_size=4), initial_count=6),
            PoolSearchSpec(NSGA3Adapter(name="population_b", population_size=3, offspring_size=3), initial_count=2),
        ]
    return PoolSearchAdapter(
        producer=producer, searches=searches,
        stagnation_steps=stagnation_steps, recovery_steps=recovery_steps,
    )
