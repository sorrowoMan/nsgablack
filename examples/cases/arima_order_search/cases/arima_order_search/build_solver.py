# -*- coding: utf-8 -*-
"""ARIMA order search via Differential Evolution on nsgablack.

Searches (p, d, q) to minimize AIC on a synthetic ARIMA time series.
Compares DE-found orders against ground truth and grid search baseline.

Usage:
  python run_solver.py --seed 42 --pop-size 20 --max-steps 80
  python run_solver.py --check
"""

from __future__ import annotations

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


def build_solver(
    *,
    pop_size: int = 20,
    max_steps: int = 80,
    resource_context=None,
    component_overrides=None,
):
    """Assemble the canonical ARIMA order-search Case."""

    overrides = dict(component_overrides or {})
    case_config = dict(overrides.pop("config", {}) or {})
    pop_size = max(4, int(case_config.get("pop_size", pop_size)))
    max_steps = max(1, int(case_config.get("max_steps", max_steps)))
    problem = overrides.pop("problem", None)
    if problem is None:
        series = _generate_arima_series(
            ar=[0.5, -0.3],
            ma=[0.4, 0.2],
            d=1,
            n=max(40, int(case_config.get("series_length", 200))),
            seed=int(case_config.get("seed", 42)),
        )
        problem = ARIMAOrderProblem(
            series,
            max_p=max(1, int(case_config.get("max_p", 5))),
            max_d=max(0, int(case_config.get("max_d", 2))),
            max_q=max(1, int(case_config.get("max_q", 5))),
        )

    solver = ComposableSolver(
        problem=problem,
        adapter=DifferentialEvolutionAdapter(
            config=DEConfig(
                population_size=pop_size,
                batch_size=max(1, pop_size // 2),
            )
        ),
        representation_pipeline=RepresentationPipeline(
            initializer=IntegerInitializer(),
            repair=IntegerRepair(),
        ),
    )
    solver.set_max_steps(max_steps)
    from nsgablack.project import apply_solver_component_overrides

    apply_solver_component_overrides(solver, overrides)
    solver.set_resource_context(resource_context)
    return solver
