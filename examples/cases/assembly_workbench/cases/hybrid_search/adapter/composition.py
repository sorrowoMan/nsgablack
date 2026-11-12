"""以 GA→VNS→GA 返回竞争表达两轮混合搜索。"""
from functools import partial

from nsgablack.adapters import MultiStrategyConfig, NSGA2Adapter, PoolTaskSpec, StrategySpec, VNSAdapter
from nsgablack.adapters.search_plan import SearchPlanAdapter, repeat, serial, stage
from nsgablack.units import UnitBinding

from ..pipeline.population import RecipePopulationBuilder
from .operations import choose_members_and_elite, crossover_then_mutate, select_elite, select_refined


def build_adapter(settings):
    ga = NSGA2Adapter(name="ga", population_size=settings.population_size,
        offspring_size=settings.population_size,
        unit_binding=UnitBinding(RecipePopulationBuilder()),
        change=partial(crossover_then_mutate, sigma=settings.ga_sigma),
        selector=partial(choose_members_and_elite, count=settings.population_size,
                         elite_count=settings.elite_count))
    vns = VNSAdapter(name="vns", batch_size=1, k_max=3, base_sigma=settings.vns_sigma,
                     scale=1.5, max_sigma=0.3, restart_on_stagnation=False)
    plan = SearchPlanAdapter(repeat(times=settings.rounds, body=serial(
        stage("ga", steps=settings.ga_steps, label="ga"),
        stage("vns", label="vns"), stage("ga", label="return"))),
        strategies=[
            StrategySpec(ga, "ga", pool_task=PoolTaskSpec(select_refined, mode="compete",
                phases=("return",), count="all", shuffle=False, change_sources=("elite",))),
            StrategySpec(vns, "vns", pool_task=PoolTaskSpec(select_elite, mode="refine",
                count="all", steps=settings.local_steps, shuffle=False, output="refined")),
        ], config=MultiStrategyConfig(total_batch_size=settings.population_size, adapt_weights=False),
        name="recipe_search")
    return plan
