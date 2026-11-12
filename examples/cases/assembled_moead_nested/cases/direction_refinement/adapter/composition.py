"""MOEA/D 方向视图 → 粗 VNS 结果视图 → 细 VNS → MOEA/D 自身竞争。"""
from nsgablack.adapters import (
    MOEADAdapter, MultiStrategyConfig, PoolTaskSpec, RoleSpec,
    StrategyRouterAdapter, VNSAdapter, subpools,
)
from nsgablack.representation import ContextGaussianMutation, GaussianMutation, UniformInitializer


def build_adapter(settings):
    moead = MOEADAdapter(
        name="directions", population_size=settings.directions, batch_size=3,
        neighborhood_size=3, decomposition="weighted_sum", random_seed=settings.seed,
        initializer=UniformInitializer(low=-2.0, high=2.0),
        mutator=GaussianMutation(sigma=0.3),
    )
    coarse = VNSAdapter(
        name="coarse_vns", batch_size=settings.neighborhood_batch,
        base_sigma=0.35, restart_on_stagnation=False,
        mutator=ContextGaussianMutation(base_sigma=0.35),
    )
    fine = VNSAdapter(
        name="fine_vns", batch_size=settings.neighborhood_batch,
        base_sigma=0.08, restart_on_stagnation=False,
        mutator=ContextGaussianMutation(base_sigma=0.08),
    )

    def phase_policy(context):
        # all(...) 只选当前可读视图，完成屏障必须在调度策略明确表达。
        if context["step"] < settings.bootstrap_steps or not moead.pool_views_ready:
            return "bootstrap"
        tasks = context["pool_tasks"]
        if tasks["coarse:0"]["status"] != "done":
            return "coarse"
        if tasks["fine:0"]["status"] != "done":
            return "fine"
        return "return" if tasks["moead:0"]["status"] != "done" else "complete"

    return StrategyRouterAdapter(
        name="nested_directions",
        roles=[
            RoleSpec("moead", moead, pool_task=PoolTaskSpec(
                "fine_proposals", mode="compete", phases=("return",), shuffle=False)),
            RoleSpec("coarse", coarse, pool_task=PoolTaskSpec(
                subpools.all(moead), count=1, steps=settings.local_steps,
                output="coarse_proposals", shuffle=False)),
            RoleSpec("fine", fine, pool_task=PoolTaskSpec(
                subpools.all(coarse), count=1, steps=settings.local_steps,
                output="fine_proposals", shuffle=False)),
        ],
        config=MultiStrategyConfig(
            total_batch_size=settings.router_budget, adapt_weights=False,
            phase_policy=phase_policy,
            phase_roles={"bootstrap": ["moead"], "coarse": ["coarse"],
                         "fine": ["fine"], "return": ["moead"], "complete": []},
        ),
    )
