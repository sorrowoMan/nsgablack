# -*- coding: utf-8 -*-
"""ARIMA order search via Differential Evolution on nsgablack.

Searches (p, d, q) to minimize AIC on a synthetic ARIMA time series.
Compares DE-found orders against ground truth and grid search baseline.

Usage:
  python build_solver.py --seed 42 --pop-size 20 --max-steps 80
  python build_solver.py --check
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _bootstrap import ensure_nsgablack_importable

ensure_nsgablack_importable(Path(__file__))

import numpy as np

from nsgablack.adapters import DEConfig, DifferentialEvolutionAdapter
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.integer import IntegerInitializer, IntegerRepair

from problem.arima_order_problem import ARIMAOrderProblem


def _generate_arima_series(
    ar: list[float],
    ma: list[float],
    d: int,
    n: int = 200,
    seed: int = 42,
) -> np.ndarray:
    from statsmodels.tsa.arima_process import ArmaProcess

    rng = np.random.default_rng(int(seed))
    ar_poly = np.r_[1.0, -np.array(ar, dtype=float)]
    ma_poly = np.r_[1.0, np.array(ma, dtype=float)]
    arma = ArmaProcess(ar_poly, ma_poly)
    diffed = arma.generate_sample(nsample=int(n), distrvs=rng.standard_normal)
    series = np.asarray(diffed, dtype=float)
    for _ in range(int(d)):
        series = np.cumsum(series)
    return series


def _grid_search_aic(
    series: np.ndarray,
    max_p: int = 5,
    max_d: int = 2,
    max_q: int = 5,
) -> tuple[tuple[int, int, int] | None, float]:
    from statsmodels.tsa.arima.model import ARIMA

    best_aic = np.inf
    best_order = None
    for p in range(max_p + 1):
        for d in range(max_d + 1):
            for q in range(max_q + 1):
                if p == 0 and q == 0:
                    continue
                try:
                    model = ARIMA(series, order=(p, d, q))
                    fit = model.fit()
                    aic = float(fit.aic)
                    if aic < best_aic:
                        best_aic = aic
                        best_order = (p, d, q)
                except Exception:
                    pass
    return best_order, best_aic


def _try_pmdarima(series: np.ndarray) -> tuple[tuple[int, int, int] | None, float | None]:
    try:
        import pmdarima as pm

        auto = pm.auto_arima(
            series,
            max_p=5,
            max_d=2,
            max_q=5,
            seasonal=False,
            trace=False,
            error_action="ignore",
            suppress_warnings=True,
        )
        order = (int(auto.order[0]), int(auto.order[1]), int(auto.order[2]))
        aic = float(auto.aic())
        return order, aic
    except Exception:
        return None, None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ARIMA order search via Differential Evolution.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--pop-size", type=int, default=20, help="DE population size.")
    parser.add_argument("--max-steps", type=int, default=80, help="Max DE generations.")
    parser.add_argument("--n-samples", type=int, default=200, help="Synthetic series length.")
    parser.add_argument("--check", action="store_true", help="Validate assembly only.")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    true_order = (2, 1, 2)
    series = _generate_arima_series(
        ar=[0.5, -0.3],
        ma=[0.4, 0.2],
        d=1,
        n=args.n_samples,
        seed=args.seed,
    )

    problem = ARIMAOrderProblem(series, max_p=5, max_d=2, max_q=5)

    pipeline = RepresentationPipeline(
        initializer=IntegerInitializer(),
        repair=IntegerRepair(),
    )

    de_config = DEConfig(
        population_size=args.pop_size,
        batch_size=max(1, args.pop_size // 2),
    )
    adapter = DifferentialEvolutionAdapter(config=de_config)

    solver = ComposableSolver(
        problem=problem,
        adapter=adapter,
        representation_pipeline=pipeline,
    )
    solver.set_random_seed(args.seed)

    if bool(args.check):
        print(
            f"[check] assembly ok | "
            f"problem={type(problem).__name__} | "
            f"pipeline={type(pipeline).__name__} | "
            f"adapter={type(adapter).__name__} | "
            f"pop_size={args.pop_size} | "
            f"max_steps={args.max_steps}"
        )
        return

    result = solver.run(max_steps=args.max_steps)

    best_x = solver.best_x
    best_obj = solver.best_objective
    if best_x is None:
        print("[arima_order_search] no best solution found")
        return

    p = int(round(float(best_x[0])))
    d = int(round(float(best_x[1])))
    q = int(round(float(best_x[2])))

    print(f"True order:       {true_order}")
    print(f"DE best order:    ({p}, {d}, {q})")
    print(f"DE best AIC:      {best_obj:.4f}")
    print(f"Evaluations:      {problem.evaluation_count}")
    print(f"Steps executed:   {result.get('steps_executed', result.get('steps', 0))}")

    gs_order, gs_aic = _grid_search_aic(series)
    if gs_order is not None:
        match = "==" if gs_order == true_order else "!="
        print(f"Grid search best: {gs_order}  (AIC={gs_aic:.4f})  {match} true")
    else:
        print("Grid search:      failed")

    pm_order, pm_aic = _try_pmdarima(series)
    if pm_order is not None:
        match = "==" if pm_order == true_order else "!="
        print(f"pmdarima order:   {pm_order}  (AIC={pm_aic:.4f})  {match} true")
    else:
        print("pmdarima:         not installed")


if __name__ == "__main__":
    main()
