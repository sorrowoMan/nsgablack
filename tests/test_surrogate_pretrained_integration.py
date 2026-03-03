import numpy as np


def test_surrogate_plugin_accepts_pretrained_model_without_online_training():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.plugins import SurrogateEvaluationPlugin, SurrogateEvaluationConfig

    class DummySurrogate:
        def predict(self, X):
            X = np.asarray(X, dtype=float)
            # simple deterministic score: sum(x^2)
            y = np.sum(X * X, axis=1, keepdims=True)
            return y

        def uncertainty(self, X):
            X = np.asarray(X, dtype=float)
            # constant uncertainty
            return np.ones((X.shape[0], 1), dtype=float) * 0.1

        def fit(self, X, Y):
            raise AssertionError("fit should not be called when online_training=False")

    class Sphere(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="sphere", dimension=2, bounds={f"x{i}": (-1.0, 1.0) for i in range(2)})

        def evaluate(self, x):
            x = np.asarray(x, dtype=float)
            return float(np.sum(x * x))

    class Fixed(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="fixed")

        def propose(self, solver, context):
            return [
                np.array([0.0, 0.0], dtype=float),
                np.array([0.5, 0.0], dtype=float),
                np.array([0.0, 0.5], dtype=float),
            ]

    solver = ComposableSolver(problem=Sphere(), adapter=Fixed())
    solver.max_steps = 1

    cfg = SurrogateEvaluationConfig(min_train_samples=0, min_true_evals=0, topk_exploit=0, topk_explore=0, retrain_every_call=False)
    solver.add_plugin(SurrogateEvaluationPlugin(config=cfg, surrogate=DummySurrogate(), online_training=False))
    solver.run()

    assert solver.objectives is not None
    # since we used pure surrogate prediction and no bias, values should match sum(x^2)
    assert float(solver.objectives[0, 0]) == 0.0

