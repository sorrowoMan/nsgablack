import os
import sys

import numpy as np


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from bias import OptimizationContext
from bias.algorithmic import (
    SimulatedAnnealingBias,
    AdaptiveSABias,
    MultiObjectiveSABias,
    DifferentialEvolutionBias,
    AdaptiveDEBias,
    PatternSearchBias,
    AdaptivePatternSearchBias,
    CoordinateDescentBias,
    GradientDescentBias,
    MomentumGradientDescentBias,
    AdaptiveGradientDescentBias,
    AdamGradientBias,
    NSGA2Bias,
    AdaptiveNSGA2Bias,
    DiversityPreservingNSGA2Bias,
)


def _build_population(dim: int, size: int, seed: int):
    rng = np.random.default_rng(seed)
    return [rng.uniform(-1.0, 1.0, size=dim) for _ in range(size)]


def _sphere(x):
    return float(np.sum(np.square(x)))


def _base_context(population, generation: int, metrics=None, evaluate=None):
    metrics = metrics or {}
    ctx = OptimizationContext(
        generation=generation,
        individual=population[0],
        population=population,
        metrics=metrics,
    )
    if evaluate is not None:
        ctx.evaluate = evaluate
    if "fitness" in metrics:
        ctx.fitness = metrics["fitness"]
    elif evaluate is not None:
        ctx.fitness = [evaluate(ind) for ind in population]
    else:
        ctx.fitness = None
    return ctx


def demo_sa_biases():
    print("== Simulated Annealing Biases ==")
    pop = _build_population(dim=5, size=6, seed=10)
    metrics = {"current_energy": 1.2, "previous_energy": 1.6}
    ctx = _base_context(pop, generation=3, metrics=metrics)
    for bias in (SimulatedAnnealingBias(), AdaptiveSABias(), MultiObjectiveSABias()):
        val = bias.compute(pop[1], ctx)
        print(f"{bias.name}: {val:.6f}")


def demo_de_biases():
    print("== Differential Evolution Biases ==")
    pop = _build_population(dim=5, size=8, seed=11)
    ctx = _base_context(pop, generation=2, metrics={"objective": _sphere(pop[0])})
    for bias in (DifferentialEvolutionBias(), AdaptiveDEBias()):
        val = bias.compute(pop[2], ctx)
        print(f"{bias.name}: {val:.6f}")


def demo_pattern_search_biases():
    print("== Pattern Search Biases ==")
    pop = _build_population(dim=5, size=6, seed=12)
    ctx = _base_context(pop, generation=1, evaluate=_sphere)
    for bias in (PatternSearchBias(), AdaptivePatternSearchBias(), CoordinateDescentBias()):
        val = bias.compute(pop[3], ctx)
        print(f"{bias.name}: {val:.6f}")


def demo_gradient_biases():
    print("== Gradient Descent Biases ==")
    pop = _build_population(dim=5, size=6, seed=13)
    ctx = _base_context(pop, generation=1, evaluate=_sphere)
    for bias in (
        GradientDescentBias(),
        MomentumGradientDescentBias(),
        AdaptiveGradientDescentBias(),
        AdamGradientBias(),
    ):
        val = bias.compute(pop[4], ctx)
        print(f"{bias.name}: {val:.6f}")


def demo_nsga2_biases():
    print("== NSGA-II Biases ==")
    pop = _build_population(dim=5, size=8, seed=14)
    metrics = {"objective": _sphere(pop[0])}
    ctx = _base_context(pop, generation=2, metrics=metrics)
    for bias in (NSGA2Bias(), AdaptiveNSGA2Bias(), DiversityPreservingNSGA2Bias()):
        val = bias.compute(pop[5], ctx)
        print(f"{bias.name}: {val:.6f}")


def main():
    demo_sa_biases()
    demo_de_biases()
    demo_pattern_search_biases()
    demo_gradient_biases()
    demo_nsga2_biases()
    print("\nAll algorithmic bias demos (full set) ran successfully.")


if __name__ == "__main__":
    main()
