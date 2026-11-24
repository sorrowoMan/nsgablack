"""可选的池驱动搜索装配；在 build_solver 中显式选择，不自动启用。"""
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
