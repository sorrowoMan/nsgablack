import os
import sys
from typing import Dict, Tuple

import numpy as np


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.base import BlackBoxProblem
from core.solver import BlackBoxSolverNSGAII
from solvers.multi_agent import MultiAgentBlackBoxSolver
from bias import (
    BiasModule,
    OptimizationContext,
    ParticleSwarmBias,
    AdaptivePSOBias,
    CMAESBias,
    AdaptiveCMAESBias,
    TabuSearchBias,
    LevyFlightBias,
)
from utils.parallel_evaluator import ParallelEvaluator
from utils.representation import (
    RepresentationPipeline,
    UniformInitializer,
    GaussianMutation,
    ClipRepair,
    IntegerInitializer,
    IntegerMutation,
    IntegerRepair,
    RandomKeyInitializer,
    RandomKeyMutation,
    RandomKeyPermutationDecoder,
    PermutationInitializer,
    PermutationSwapMutation,
    PermutationInversionMutation,
    PermutationRepair,
    BinaryInitializer,
    BitFlipMutation,
    BinaryRepair,
    BinaryCapacityRepair,
    GraphEdgeInitializer,
    GraphEdgeMutation,
    GraphConnectivityRepair,
    GraphDegreeRepair,
    IntegerMatrixInitializer,
    IntegerMatrixMutation,
    MatrixRowColSumRepair,
    MatrixSparsityRepair,
    MatrixBlockSumRepair,
)


class MiniSphereProblem(BlackBoxProblem):
    def __init__(self, dimension: int = 6, bounds: Dict[str, Tuple[float, float]] = None):
        if bounds is None:
            bounds = {f"x{i}": (-2.0, 2.0) for i in range(dimension)}
        super().__init__(name="MiniSphere", dimension=dimension, bounds=bounds)

    def evaluate(self, x: np.ndarray):
        return float(np.sum(np.square(x)))

    def evaluate_constraints(self, x: np.ndarray):
        # Simple constraint: sum(x) <= 1.0
        return np.array([np.sum(x) - 1.0], dtype=float)


def _assert_shape(vec: np.ndarray, expected_len: int, name: str):
    if vec.shape[0] != expected_len:
        raise AssertionError(f"{name} expected length {expected_len}, got {vec.shape[0]}")


def check_basic_tools_and_bias():
    print("[1/4] basic tools + bias")
    np.random.seed(7)
    problem = MiniSphereProblem(dimension=6)

    # Representation pipeline
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-2.0, high=2.0),
        mutator=GaussianMutation(sigma=0.4),
        repair=ClipRepair(low=-2.0, high=2.0),
    )

    # Bias module
    bias = BiasModule()
    bias.add_penalty(lambda x: max(0.0, np.sum(x) - 1.0), weight=5.0, name="sum_constraint")
    bias.add_reward(lambda x: max(0.0, 1.0 - np.mean(np.abs(x))), weight=0.05, name="small_values")

    solver = BlackBoxSolverNSGAII(problem)
    solver.enable_bias = True
    solver.bias_module = bias
    solver.enable_progress_log = False
    solver.pop_size = 20
    solver.max_generations = 4
    solver.set_representation_pipeline(pipeline)
    solver.run()

    # Basic tool: parallel evaluator (thread backend to avoid multiprocessing overhead)
    evaluator = ParallelEvaluator(backend="thread", max_workers=2, verbose=False)
    population = np.random.uniform(-2.0, 2.0, size=(10, problem.dimension))
    result = evaluator.evaluate_population(
        population,
        problem,
        enable_bias=True,
        bias_module=bias,
        return_detailed=True,
    )
    if not result or "objectives" not in result:
        raise AssertionError("ParallelEvaluator returned no objectives")

    print("  OK: solver + bias + parallel evaluator")


def check_multi_agent_with_bias_profiles():
    print("[2/4] multi-agent + built-in bias profiles + representation pipeline")
    np.random.seed(13)
    problem = MiniSphereProblem(dimension=5)

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-1.5, high=1.5),
        mutator=GaussianMutation(sigma=0.3),
        repair=ClipRepair(low=-1.5, high=1.5),
    )

    config = {
        "total_population": 30,
        "max_generations": 3,
        "communication_interval": 2,
        "adaptation_interval": 2,
        "use_bias_system": True,
        "representation_pipeline": pipeline,
    }

    solver = MultiAgentBlackBoxSolver(problem, config=config)
    pareto = solver.run()

    if pareto is None:
        raise AssertionError("Multi-agent returned no result")
    print("  OK: multi-agent run completed")


def check_representation_modules():
    print("[3/4] representation modules smoke check")
    np.random.seed(21)

    class DummyProblem(BlackBoxProblem):
        def __init__(self):
            bounds = {f"x{i}": (-3, 3) for i in range(6)}
            super().__init__(name="Dummy", dimension=6, bounds=bounds)
            self.num_nodes = 5
            self.matrix_shape = (3, 3)

        def evaluate(self, x):
            return float(np.sum(np.square(x)))

    problem = DummyProblem()

    # Continuous
    x = UniformInitializer(low=-1.0, high=1.0).initialize(problem)
    x = GaussianMutation(sigma=0.2).mutate(x)
    x = ClipRepair(low=-1.0, high=1.0).repair(x, context={"problem": problem})
    _assert_shape(x, problem.dimension, "continuous")

    # Integer
    x = IntegerInitializer().initialize(problem)
    x = IntegerMutation(sigma=1.0).mutate(x, context={"problem": problem})
    x = IntegerRepair().repair(x, context={"problem": problem})
    _assert_shape(x, problem.dimension, "integer")

    # Permutation + random keys
    perm = PermutationInitializer().initialize(problem)
    perm = PermutationSwapMutation().mutate(perm)
    perm = PermutationInversionMutation().mutate(perm)
    perm = PermutationRepair().repair(perm)
    _assert_shape(perm, problem.dimension, "permutation")

    rk = RandomKeyInitializer().initialize(problem)
    rk = RandomKeyMutation().mutate(rk)
    decoded = RandomKeyPermutationDecoder().decode(rk)
    _assert_shape(decoded, problem.dimension, "random-keys")

    # Binary
    b = BinaryInitializer().initialize(problem)
    b = BitFlipMutation(rate=0.2).mutate(b)
    b = BinaryRepair().repair(b)
    b = BinaryCapacityRepair(capacity=3, exact=True).repair(b)
    _assert_shape(b, problem.dimension, "binary")

    # Graph
    g = GraphEdgeInitializer(num_nodes=problem.num_nodes, density=0.3).initialize(problem)
    g = GraphEdgeMutation(rate=0.1).mutate(g)
    g = GraphConnectivityRepair().repair(g, context={"num_nodes": problem.num_nodes})
    g = GraphDegreeRepair(min_degree=1, max_degree=3).repair(g, context={"num_nodes": problem.num_nodes})
    expected_edges = problem.num_nodes * (problem.num_nodes - 1) // 2
    _assert_shape(g, expected_edges, "graph")

    # Matrix
    m = IntegerMatrixInitializer(rows=3, cols=3, low=0, high=5).initialize(problem)
    m = IntegerMatrixMutation(sigma=1.0, low=0, high=5).mutate(m)
    m = MatrixRowColSumRepair(row_sums=np.array([3, 3, 3]), col_sums=np.array([3, 3, 3])).repair(
        m, context={"shape": (3, 3)}
    )
    m = MatrixSparsityRepair(k_nonzero=4).repair(m)
    m = MatrixBlockSumRepair(block_shape=(1, 1), block_min=0, block_max=5, low=0, high=5).repair(
        m, context={"shape": (3, 3)}
    )
    _assert_shape(m, 9, "matrix")

    print("  OK: representation modules")


def check_algorithmic_biases():
    print("[4/4] algorithmic bias smoke check")
    np.random.seed(33)
    pop = [np.random.uniform(-1.0, 1.0, size=5) for _ in range(6)]
    mean = np.mean(np.asarray(pop), axis=0)
    cov = np.cov(np.asarray(pop).T)
    metrics = {
        "objective": float(np.sum(pop[0] ** 2)),
        "global_best_x": pop[0],
        "local_best_x": pop[1],
        "mean": mean,
        "cov": cov,
        "sigma": 0.5,
        "max_generations": 10,
    }
    ctx = OptimizationContext(generation=3, individual=pop[2], population=pop, metrics=metrics)

    biases = [
        ParticleSwarmBias(),
        AdaptivePSOBias(),
        CMAESBias(),
        AdaptiveCMAESBias(),
        TabuSearchBias(),
        LevyFlightBias(),
    ]

    for bias in biases:
        val = bias.compute(pop[2], ctx)
        if not isinstance(val, float):
            raise AssertionError(f"{bias.name} returned non-float")

    # Exercise tabu memory with another call
    _ = biases[4].compute(pop[3], ctx)
    print("  OK: algorithmic biases")


def main():
    failures = []
    for fn in (
        check_basic_tools_and_bias,
        check_multi_agent_with_bias_profiles,
        check_representation_modules,
        check_algorithmic_biases,
    ):
        try:
            fn()
        except Exception as exc:
            failures.append((fn.__name__, exc))

    if failures:
        print("\nValidation failures:")
        for name, exc in failures:
            print(f"  - {name}: {exc}")
        raise SystemExit(1)

    print("\nAll validation checks passed.")


if __name__ == "__main__":
    main()
