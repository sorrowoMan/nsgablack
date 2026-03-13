"""Problem construction helpers for production_scheduling case."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from refactor_data import load_production_data

from .production_problem import ProductionConstraints, ProductionSchedulingProblem

_PROBLEM_FACTORY_CACHE = {}


class ProductionProblemFactory:
    """Picklable factory for multiprocessing parallel evaluation."""

    def __init__(
        self,
        *,
        base_dir: str,
        bom: Optional[str],
        supply: Optional[str],
        machines: int,
        materials: int,
        days: int,
        max_machines: int,
        min_machines: int,
        min_prod: int,
        max_prod: int,
        shortage_unit_penalty: float,
        penalty_objective: bool,
        penalty_scale: float,
    ) -> None:
        self.base_dir = str(base_dir)
        self.bom = bom
        self.supply = supply
        self.machines = int(machines)
        self.materials = int(materials)
        self.days = int(days)
        self.max_machines = int(max_machines)
        self.min_machines = int(min_machines)
        self.min_prod = int(min_prod)
        self.max_prod = int(max_prod)
        self.shortage_unit_penalty = float(shortage_unit_penalty)
        self.penalty_objective = bool(penalty_objective)
        self.penalty_scale = float(penalty_scale)
        self._cache_key = (
            self.base_dir,
            self.bom,
            self.supply,
            self.machines,
            self.materials,
            self.days,
            self.max_machines,
            self.min_machines,
            self.min_prod,
            self.max_prod,
            self.shortage_unit_penalty,
            self.penalty_objective,
            self.penalty_scale,
        )

    def __call__(self) -> ProductionSchedulingProblem:
        cached = _PROBLEM_FACTORY_CACHE.get(self._cache_key)
        if cached is not None:
            return cached

        base_dir = Path(self.base_dir)
        data = load_production_data(
            base_dir=base_dir,
            bom_path=Path(self.bom) if self.bom else None,
            supply_path=Path(self.supply) if self.supply else None,
            machines=self.machines,
            materials=self.materials,
            days=self.days,
            fallback=True,
        )
        constraints = ProductionConstraints(
            max_machines_per_day=self.max_machines,
            min_machines_per_day=self.min_machines,
            min_production_per_machine=self.min_prod,
            max_production_per_machine=self.max_prod,
            shortage_unit_penalty=self.shortage_unit_penalty,
            include_penalty_objective=self.penalty_objective,
            penalty_objective_scale=self.penalty_scale,
        )
        problem = ProductionSchedulingProblem(data=data, constraints=constraints)
        _PROBLEM_FACTORY_CACHE[self._cache_key] = problem
        return problem


def build_problem_factory(args, *, base_dir: Path) -> ProductionProblemFactory:
    return ProductionProblemFactory(
        base_dir=str(base_dir),
        bom=args.bom,
        supply=args.supply,
        machines=args.machines,
        materials=args.materials,
        days=args.days,
        max_machines=args.max_machines,
        min_machines=args.min_machines,
        min_prod=args.min_prod,
        max_prod=args.max_prod,
        shortage_unit_penalty=args.shortage_unit_penalty,
        penalty_objective=args.penalty_objective,
        penalty_scale=args.penalty_scale,
    )


def build_problem(
    args,
    *,
    base_dir: Path,
    print_paths: bool = True,
) -> ProductionSchedulingProblem:
    data = load_production_data(
        base_dir=base_dir,
        bom_path=Path(args.bom) if args.bom else None,
        supply_path=Path(args.supply) if args.supply else None,
        machines=args.machines,
        materials=args.materials,
        days=args.days,
        fallback=True,
    )
    if print_paths:
        if getattr(data, "bom_path", None) is not None:
            print(f"[data] bom={data.bom_path}")
        if getattr(data, "supply_path", None) is not None:
            print(f"[data] supply={data.supply_path}")
    constraints = ProductionConstraints(
        max_machines_per_day=args.max_machines,
        min_machines_per_day=args.min_machines,
        min_production_per_machine=args.min_prod,
        max_production_per_machine=args.max_prod,
        shortage_unit_penalty=args.shortage_unit_penalty,
        include_penalty_objective=args.penalty_objective,
        penalty_objective_scale=args.penalty_scale,
    )
    return ProductionSchedulingProblem(data=data, constraints=constraints)
