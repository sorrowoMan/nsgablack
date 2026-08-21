"""Canonical ARIMA order-search Case CLI."""

from __future__ import annotations

import argparse
import warnings

from build_solver import (
    _generate_arima_series,
    _grid_search_aic,
    _try_pmdarima,
    build_solver,
)
from problem.arima_order_problem import ARIMAOrderProblem

from nsgablack.project.scaffold import print_solver_check


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ARIMA order search via Differential Evolution")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--pop-size", type=int, default=20)
    parser.add_argument("--max-steps", type=int, default=80)
    parser.add_argument("--n-samples", type=int, default=200)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    warnings.filterwarnings("ignore")
    true_order = (2, 1, 2)
    series = _generate_arima_series(
        ar=[0.5, -0.3],
        ma=[0.4, 0.2],
        d=1,
        n=args.n_samples,
        seed=args.seed,
    )
    problem = ARIMAOrderProblem(series, max_p=5, max_d=2, max_q=5)
    solver = build_solver(
        pop_size=args.pop_size,
        max_steps=args.max_steps,
        component_overrides={"problem": problem},
    )
    solver.set_random_seed(args.seed)
    if args.check:
        print_solver_check(solver)
        return 0

    result = solver.run()
    if solver.best_x is None:
        print("[arima_order_search] no best solution found")
        return 1
    p, d, q = (int(round(float(value))) for value in solver.best_x[:3])
    print(f"True order:       {true_order}")
    print(f"DE best order:    ({p}, {d}, {q})")
    print(f"DE best AIC:      {float(solver.best_objective):.4f}")
    print(f"Evaluations:      {problem.evaluation_count}")
    print(f"Steps executed:   {result.get('steps_executed', result.get('steps', 0))}")
    grid_order, grid_aic = _grid_search_aic(series)
    if grid_order is not None:
        print(f"Grid search best: {grid_order}  (AIC={grid_aic:.4f})")
    pm_order, pm_aic = _try_pmdarima(series)
    if pm_order is not None:
        print(f"pmdarima order:   {pm_order}  (AIC={pm_aic:.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
