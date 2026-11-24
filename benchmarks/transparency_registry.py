"""公开 Adapter 的透明性覆盖登记，不把抽象基类或配置项算作算法通过。

这里只汇总配对声明。registered 表示有可执行 Case；只有传入实际运行报告，
且语义、质量和恢复均通过时才产生 passed。未来新增公开 Adapter 会显式显示缺口。
"""
from __future__ import annotations

import inspect


COVERAGE = {
    "BayesianOptimizationAdapter": ("bayesian_optimization",),
    "CMAESAdapter": ("cmaes",),
    "MapElitesAdapter": ("map_elites",),
    "SearchPlanAdapter": ("search_plan_serial", "search_plan_multi", "search_plan_nested", "pool_task"),
    "PoolSearchAdapter": ("pool_search",),
    "PoolTaskAdapter": ("pool_task",),
    "CompositeAdapter": ("composite",),
    "RoleAdapter": ("role_adapter", "role_router"),
    "RoleRouterAdapter": ("role_router",),
    "VNSAdapter": ("vns",),
    "MOEADAdapter": ("moead_zdt1",),
    "SimulatedAnnealingAdapter": ("sa",),
    "StrategyRouterAdapter": ("strategy_router",),
    "StrategyChainAdapter": ("strategy_chain",),
    "AStarAdapter": ("astar",),
    "MOAStarAdapter": ("moa_star",),
    "TrustRegionDFOAdapter": ("trust_region_dfo",),
    "TrustRegionMODFOAdapter": ("trust_region_mo_dfo",),
    "TrustRegionSubspaceAdapter": ("trust_region_subspace",),
    "TrustRegionNonSmoothAdapter": ("trust_region_nonsmooth",),
    "MASAdapter": ("mas",),
    "AsyncEventDrivenAdapter": ("async_event_driven_cases", "async_event_driven_weighted"),
    "SingleTrajectoryAdaptiveAdapter": ("single_trajectory_adaptive",),
    "DifferentialEvolutionAdapter": ("de_zdt1",),
    "GradientDescentAdapter": ("gradient_descent",),
    "GradientOptimizerAdapter": ("gradient_optimizer_sgd", "gradient_optimizer_adam", "gradient_optimizer_adamw"),
    "GaussianSearchAdapter": ("gaussian_search",),
    "FixedCandidateAdapter": ("fixed_candidate",),
    "EliteRetentionAdapter": ("elite_retention",),
    "PatternSearchAdapter": ("pattern_search",),
    "NSGA2Adapter": ("nsga2_zdt1",),
    "NSGA3Adapter": ("nsga3_zdt1", "nsga3_dtlz2"),
    "SPEA2Adapter": ("spea2_zdt1",),
}

BASE_CONTRACT_FIXTURES = {
    "AlgorithmAdapter": (),
    "UnitBackedAdapter": (),
    "CandidateProposerAdapter": ("candidate_proposer_contract",),
}


def specs(*, population_size=10, steps=6):
    from benchmarks.transparency_population import specs as population
    from benchmarks.transparency_trajectory import specs as trajectory
    from benchmarks.transparency_structured import specs as structured
    from benchmarks.transparency_composition import specs as composition
    from benchmarks.transparency_protocols import specs as protocols

    result = [*population(population_size=population_size, steps=steps),
              *trajectory(), *structured(), *composition(), *protocols()]
    names = [spec.name for spec in result]
    if len(names) != len(set(names)):
        raise ValueError("transparency PairSpec names must be unique")
    return result


def by_name(name, *, population_size=10, steps=6):
    for spec in specs(population_size=population_size, steps=steps):
        if spec.name == name:
            return spec
    raise KeyError(f"unknown transparency Case: {name}")


def export_inventory():
    """Inspect every __all__ name without creating an Adapter or Unit."""
    from nsgablack import adapters

    result, seen = [], {}
    for name in adapters.__all__:
        value = getattr(adapters, name)
        is_class = inspect.isclass(value)
        adapter = is_class and issubclass(value, adapters.AlgorithmAdapter)
        identity = f"{getattr(value, '__module__', type(value).__module__)}.{getattr(value, '__qualname__', type(value).__qualname__)}"
        alias_of = seen.get(id(value))
        renamed = (inspect.isclass(value) or inspect.isfunction(value)) and getattr(value, "__name__", name) != name
        if adapter and inspect.isabstract(value):
            category = "abstract_adapter"
        elif adapter:
            category = "concrete_adapter"
        elif alias_of is not None or renamed:
            category = "public_alias"
        elif is_class:
            category = "support_type"
        else:
            category = "support_helper"
        row = {"name": name, "classification": category, "identity": identity, "is_adapter": adapter}
        if alias_of is not None or renamed:
            row["alias_target"] = alias_of or identity
        if adapter:
            row["abstract_methods"] = sorted(getattr(value, "__abstractmethods__", ()))
        result.append(row)
        seen.setdefault(id(value), name)
    return result


def coverage_report(results=None, *, population_size=10, steps=6):
    """Apply actual reports to concrete classes; abstract classes never pass.

    results may contain multiple seeds. Every supplied result for a required
    Case must pass semantics, quality and recovery. Missing, unsupported or
    failed quality evidence cannot satisfy the gate; missing cases remain
    unverified. This status covers only the Case's declared task and branches.
    """
    declared = {spec.name for spec in specs(population_size=population_size, steps=steps)}
    observed = {}
    for report in results or ():
        observed.setdefault(report["name"], []).append(report)
    inventory = export_inventory()
    concrete, bases = [], []
    for export in inventory:
        name = export["name"]
        if export["classification"] == "abstract_adapter":
            bases.append({"name": name, "status": "abstract_not_an_algorithm",
                          "contract_fixtures": list(BASE_CONTRACT_FIXTURES.get(name, ())),
                          "counted_as_passed": False, "abstract_methods": export["abstract_methods"]})
        elif export["classification"] == "concrete_adapter":
            cases = COVERAGE.get(name, ())
            missing = [case for case in cases if case not in declared]
            if not cases or missing:
                status = "uncovered"
            elif results is None:
                status = "registered"
            elif any(case not in observed for case in cases):
                status = "unverified"
            elif all(report.get("semantics", {}).get("status") == "passed"
                     and report.get("quality", {}).get("status") == "passed"
                     and report.get("recovery", {}).get("status") == "passed"
                     for case in cases for report in observed[case]):
                status = "passed"
            else:
                status = "failed"
            concrete.append({"name": name, "cases": list(cases), "status": status,
                             "missing_registered_cases": missing})
    return {"public_exports": inventory, "concrete_adapters": concrete, "abstract_adapters": bases,
            "summary": {"public_export_count": len(inventory), "concrete_adapter_count": len(concrete),
                        "abstract_adapter_count": len(bases), "paired_case_count": len(declared),
                        "concrete_passed": sum(row["status"] == "passed" for row in concrete),
                        "concrete_registered": sum(row["status"] == "registered" for row in concrete),
                        "concrete_uncovered": sum(row["status"] == "uncovered" for row in concrete)},
            "required_checks": ["semantics", "quality", "recovery"],
            "interpretation": "Passed requires semantics, quality and recovery passed for every observed report of every mapped Case. Missing or unsupported checks do not pass. Registered fixtures are not execution evidence. Base-contract fixtures never count as concrete algorithms.",
            "coverage_scope": "Small deterministic task families; per-Case metadata lists limits. This is not every parameter/provider/mathematical branch."}


__all__ = ["COVERAGE", "BASE_CONTRACT_FIXTURES", "specs", "by_name", "export_inventory", "coverage_report"]
