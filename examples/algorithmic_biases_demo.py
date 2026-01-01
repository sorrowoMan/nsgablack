import os
import sys

import numpy as np


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from bias import OptimizationContext
from bias.algorithmic import (
    ParticleSwarmBias,
    AdaptivePSOBias,
    CMAESBias,
    AdaptiveCMAESBias,
    TabuSearchBias,
    LevyFlightBias,
)


def _build_population(dim: int, size: int, seed: int):
    rng = np.random.default_rng(seed)
    return [rng.uniform(-1.0, 1.0, size=dim) for _ in range(size)]


def _base_context(population, generation: int, metrics=None):
    metrics = metrics or {}
    return OptimizationContext(
        generation=generation,
        individual=population[0],
        population=population,
        metrics=metrics,
    )


def demo_pso_bias():
    print("== PSO Bias ==")
    pop = _build_population(dim=5, size=6, seed=1)
    metrics = {
        "global_best_x": pop[0],
        "local_best_x": pop[1],
        "max_generations": 10,
    }
    ctx = _base_context(pop, generation=3, metrics=metrics)
    bias = ParticleSwarmBias()
    val = bias.compute(pop[2], ctx)
    print(f"bias={val:.6f}")


def demo_adaptive_pso_bias():
    print("== Adaptive PSO Bias ==")
    pop = _build_population(dim=5, size=6, seed=2)
    metrics = {
        "global_best_x": pop[0],
        "local_best_x": pop[1],
        "max_generations": 10,
    }
    ctx = _base_context(pop, generation=6, metrics=metrics)
    bias = AdaptivePSOBias()
    val = bias.compute(pop[3], ctx)
    print(f"bias={val:.6f}")


def demo_cma_es_bias():
    print("== CMA-ES Bias ==")
    pop = _build_population(dim=5, size=6, seed=3)
    mean = np.mean(np.asarray(pop), axis=0)
    cov = np.cov(np.asarray(pop).T)
    metrics = {
        "mean": mean,
        "cov": cov,
        "sigma": 0.5,
    }
    ctx = _base_context(pop, generation=2, metrics=metrics)
    bias = CMAESBias()
    val = bias.compute(pop[4], ctx)
    print(f"bias={val:.6f}")


def demo_adaptive_cma_es_bias():
    print("== Adaptive CMA-ES Bias ==")
    pop = _build_population(dim=5, size=6, seed=4)
    mean = np.mean(np.asarray(pop), axis=0)
    cov = np.cov(np.asarray(pop).T)
    metrics = {
        "mean": mean,
        "cov": cov,
        "sigma": 0.5,
        "max_generations": 20,
    }
    ctx = _base_context(pop, generation=10, metrics=metrics)
    bias = AdaptiveCMAESBias()
    val = bias.compute(pop[5], ctx)
    print(f"bias={val:.6f}")


def demo_tabu_search_bias():
    print("== Tabu Search Bias ==")
    pop = _build_population(dim=5, size=6, seed=5)
    ctx = _base_context(pop, generation=1)
    bias = TabuSearchBias(tabu_size=3, distance_threshold=0.5)
    val1 = bias.compute(pop[0], ctx)
    val2 = bias.compute(pop[0], ctx)
    print(f"bias_first={val1:.6f} bias_second={val2:.6f}")


def demo_levy_flight_bias():
    print("== Levy Flight Bias ==")
    pop = _build_population(dim=5, size=6, seed=6)
    metrics = {"max_generations": 10}
    ctx = _base_context(pop, generation=2, metrics=metrics)
    bias = LevyFlightBias()
    val = bias.compute(pop[2], ctx)
    print(f"bias={val:.6f}")


def main():
    demo_pso_bias()
    demo_adaptive_pso_bias()
    demo_cma_es_bias()
    demo_adaptive_cma_es_bias()
    demo_tabu_search_bias()
    demo_levy_flight_bias()
    print("\nAll algorithmic bias demos ran successfully.")


if __name__ == "__main__":
    main()
