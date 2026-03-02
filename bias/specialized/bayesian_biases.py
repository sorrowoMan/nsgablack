"""
Bayesian bias implementations and helpers.
"""

from typing import Callable, List

import numpy as np

from ..core.base import AlgorithmicBias, OptimizationContext


class SimpleBayesianOptimizer:
    """Lightweight placeholder Bayesian optimizer used by biases."""

    def __init__(self, acquisition: str = "ei", kernel: str = "rbf"):
        self.acquisition = acquisition
        self.kernel = kernel
        self.X_observed = []
        self.y_observed = []
        self.gp = None

    def observe(self, x, y):
        """Record an observation."""
        self.X_observed.append(x.copy() if isinstance(x, np.ndarray) else x)
        self.y_observed.append(y)

    def reset(self):
        """Clear observations."""
        self.X_observed = []
        self.y_observed = []
        self.gp = None


# Alias for convenience.
BayesianOptimizer = SimpleBayesianOptimizer


class BayesianGuidanceBias(AlgorithmicBias):
    """Bayesian guidance bias for exploration/exploitation direction."""
    context_requires = ("dynamic", "generation", "individual", "population_ref")
    requires_metrics = ("objective",)
    metrics_fallback = "safe_zero"
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: dynamic, generation, individual, metrics, population_ref; outputs scalar bias only."



    def __init__(
        self,
        weight: float = 0.2,
        buffer_size: int = 50,
        acquisition: str = "ei",
        kernel: str = "rbf",
        adaptive_weight: bool = True,
        exploration_factor: float = 0.1,
    ):
        super().__init__("bayesian_guidance", weight)
        self.buffer_size = buffer_size
        self.acquisition = acquisition
        self.kernel = kernel
        self.adaptive_weight = adaptive_weight
        self.exploration_factor = exploration_factor

        self.local_bo = BayesianOptimizer(acquisition=acquisition, kernel=kernel)
        self._rng = np.random.default_rng()

        self.data_buffer = []
        self.last_update_gen = 0
        self.update_frequency = 5

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """Compute guidance bias using available context."""
        self._update_buffer(context)
        if len(self.data_buffer) < 5:
            return 0.0

        if context.generation - self.last_update_gen >= self.update_frequency:
            if hasattr(self, "problem_instance") and self.problem_instance:
                self._update_model_with_real_eval()
            else:
                self._update_model_simple()
            self.last_update_gen = context.generation

        predicted_improvement = self._predict_improvement(x, context)
        current_weight = self._adaptive_weight_adjustment(context)
        return current_weight * predicted_improvement

    def apply(
        self, x: np.ndarray, eval_func: Callable[[np.ndarray], float], context: OptimizationContext
    ) -> float:
        """Compute guidance bias using a provided evaluation function."""
        self._update_buffer(context)
        if len(self.data_buffer) < 5:
            return 0.0

        if context.generation - self.last_update_gen >= self.update_frequency:
            self._update_model(eval_func)
            self.last_update_gen = context.generation

        predicted_improvement = self._predict_improvement(x, context)
        current_weight = self._adaptive_weight_adjustment(context)
        return current_weight * predicted_improvement

    def _update_buffer(self, context: OptimizationContext):
        if context.individual is None:
            return

        value = None
        if hasattr(context, "individual_value"):
            value = context.individual_value
        elif hasattr(context, "metrics") and context.metrics and "objective" in context.metrics:
            value = context.metrics["objective"]
        elif context.population and len(context.population) > 0:
            try:
                idx = context.population.index(context.individual) if context.individual in context.population else 0
                value = len(context.population) - idx
            except Exception:
                value = 0.0
        else:
            value = 0.0

        self.data_buffer.append(
            {
                "x": context.individual.copy(),
                "y": value,
                "generation": context.generation,
            }
        )

        if len(self.data_buffer) > self.buffer_size:
            self.data_buffer.pop(0)

    def _update_model(self, eval_func: Callable[[np.ndarray], float]):
        if len(self.data_buffer) < 5:
            return

        X = np.array([item["x"] for item in self.data_buffer])
        y = np.array([item["y"] for item in self.data_buffer])

        self.local_bo.reset()
        for i in range(len(X)):
            self.local_bo.observe(X[i], y[i])

    def _update_model_simple(self):
        if len(self.data_buffer) < 5:
            return
        # No-op: keep placeholder behavior without building a surrogate.
        return

    def _update_model_with_real_eval(self):
        if len(self.data_buffer) < 5:
            return

        if self._try_update_with_nsga_surrogate():
            return
        if self._try_update_with_nsga_data():
            return

        print("Bayesian model fallback: evaluating historical points.")
        self._update_with_evaluation_function()

    def _try_update_with_nsga_surrogate(self):
        if not (
            hasattr(self, "bias_manager")
            and hasattr(self.bias_manager, "solver_instance")
            and self.bias_manager.solver_instance
        ):
            return False

        solver = self.bias_manager.solver_instance

        if not (
            hasattr(solver, "surrogate")
            and solver.surrogate is not None
            and hasattr(solver, "X_real")
            and len(solver.X_real) >= 5
        ):
            return False

        try:
            n_samples = min(500, len(solver.X_real) * 5)
            X_train = []
            y_train = []

            for i in range(n_samples):
                if i < len(solver.X_real):
                    base_idx = i % len(solver.X_real)
                    base_point = solver.X_real[base_idx]
                else:
                    base_idx = int(self._rng.integers(0, len(solver.X_real)))
                    base_point = solver.X_real[base_idx]

                noise = self._rng.normal(0, 0.1, base_point.shape)
                new_point = np.clip(base_point + noise, 0, 1)
                X_train.append(new_point)

                try:
                    pred = solver._evaluate_surrogate(new_point)
                    y_train.append(pred[0] if isinstance(pred, np.ndarray) else pred)
                except Exception:
                    y_train.append(0.0)

            X_train = np.array(X_train)
            y_train = np.array(y_train)

            self.local_bo.reset()
            for i in range(len(X_train)):
                try:
                    self.local_bo.observe(X_train[i], y_train[i])
                except Exception:
                    continue

            print(
                "Bayesian model updated using NSGA surrogate with "
                f"{len(X_train)} points (no real eval)."
            )
            return True
        except Exception as exc:
            print(f"Failed to update Bayesian model using NSGA surrogate: {exc}")

        return False

    def _try_update_with_nsga_data(self):
        if not (hasattr(self, "bias_manager") and hasattr(self.bias_manager, "get_evaluated_data")):
            return False

        X, y = self.bias_manager.get_evaluated_data()
        if X is None or y is None or len(X) == 0:
            return False

        self.local_bo.reset()
        for i in range(min(len(X), 200)):
            try:
                self.local_bo.observe(X[i], y[i])
            except Exception:
                continue

        print(
            "Bayesian model updated using NSGA evaluated data with "
            f"{len(X)} points (no re-eval)."
        )
        return True

    def _update_with_evaluation_function(self):
        X = np.array([item["x"] for item in self.data_buffer])
        y = []
        for x in X:
            try:
                objectives = self.problem_instance.evaluate(x)
                single_objective = objectives[0]
                y.append(single_objective)
            except Exception as exc:
                print(f"Failed to evaluate historical point: {exc}")
                y.append(0.0)

        y = np.array(y)

        self.local_bo.reset()
        for i in range(len(X)):
            try:
                self.local_bo.observe(X[i], y[i])
            except Exception:
                continue

        print(f"Bayesian model updated by re-evaluating {len(y)} points.")

    def _predict_improvement(self, x: np.ndarray, context: OptimizationContext) -> float:
        if len(self.data_buffer) < 5:
            return 0.0

        try:
            current_best = min(item["y"] for item in self.data_buffer)
            improvement_score = 0.0

            if hasattr(self.local_bo, "gp") and self.local_bo.gp is not None:
                mu, sigma = self.local_bo.gp.predict(x.reshape(1, -1), return_std=True)
                uncertainty_bonus = self.exploration_factor * sigma[0]
                expected_improvement = max(0, current_best - mu[0])
                improvement_score = expected_improvement + uncertainty_bonus

            if context.population:
                distances = [np.linalg.norm(x - ind) for ind in context.population]
                min_distance = min(distances)
                density_bonus = self.exploration_factor * min_distance
                improvement_score += density_bonus

            return max(0, improvement_score)
        except Exception:
            return 0.0

    def _adaptive_weight_adjustment(self, context: OptimizationContext) -> float:
        if not self.adaptive_weight:
            return self.weight

        if hasattr(context, "is_stuck") and context.is_stuck:
            return self.weight * 1.5
        if context.generation > 50:
            decay_factor = np.exp(-0.01 * (context.generation - 50))
            return self.weight * decay_factor
        return self.weight


class BayesianExplorationBias(AlgorithmicBias):
    """Bayesian exploration bias using uncertainty estimates."""
    context_requires = ("generation", "population_ref")
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: generation, population_ref; outputs scalar bias only."



    def __init__(self, weight: float = 0.3, uncertainty_threshold: float = 0.1, decay_rate: float = 0.95):
        super().__init__("bayesian_exploration", weight)
        self.uncertainty_threshold = uncertainty_threshold
        self.decay_rate = decay_rate
        self.current_weight = weight

        self.bo = BayesianOptimizer(acquisition="ucb")
        self.exploration_history = []

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        if context.population and len(context.population) > 5:
            self._collect_data_simple(context.population)

        uncertainty = self._predict_uncertainty(x)

        if uncertainty > self.uncertainty_threshold:
            exploration_bonus = uncertainty * self.current_weight
            self.exploration_history.append(
                {"x": x.copy(), "uncertainty": uncertainty, "generation": context.generation}
            )
            self.current_weight *= self.decay_rate
            return exploration_bonus

        return 0.0

    def apply(
        self, x: np.ndarray, eval_func: Callable[[np.ndarray], float], context: OptimizationContext
    ) -> float:
        if context.population and len(context.population) > 5:
            self._collect_data(context.population, eval_func)

        uncertainty = self._predict_uncertainty(x)

        if uncertainty > self.uncertainty_threshold:
            exploration_bonus = uncertainty * self.current_weight
            self.exploration_history.append(
                {"x": x.copy(), "uncertainty": uncertainty, "generation": context.generation}
            )
            self.current_weight *= self.decay_rate
            return exploration_bonus

        return 0.0

    def _collect_data(self, population: List[np.ndarray], eval_func: Callable):
        self.bo.reset()
        for ind in population:
            try:
                y = eval_func(ind)
                self.bo.observe(ind, y)
            except Exception:
                pass

    def _collect_data_simple(self, population: List[np.ndarray]):
        self.bo.reset()
        for i, ind in enumerate(population):
            estimated_value = len(population) - i
            try:
                self.bo.observe(ind, estimated_value)
            except Exception:
                pass

    def _predict_uncertainty(self, x: np.ndarray) -> float:
        if len(self.bo.X_observed) < 5:
            return 0.0

        try:
            if hasattr(self.bo, "gp") and self.bo.gp is not None:
                _, sigma = self.bo.gp.predict(x.reshape(1, -1), return_std=True)
                return sigma[0]
        except Exception:
            pass

        return 0.0


class BayesianConvergenceBias(AlgorithmicBias):
    """Bayesian convergence bias using predicted improvement trends."""
    context_requires = ()
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: metrics; outputs scalar bias only."



    def __init__(self, weight: float = 0.2, convergence_threshold: float = 1e-4, history_window: int = 20):
        super().__init__("bayesian_convergence", weight)
        self.convergence_threshold = convergence_threshold
        self.history_window = history_window

        self.predictor = BayesianOptimizer()
        self.convergence_history = []

    def apply(
        self, x: np.ndarray, eval_func: Callable[[np.ndarray], float], context: OptimizationContext
    ) -> float:
        is_converging = self._check_convergence(context)
        if not is_converging:
            return 0.0

        optimal_direction = self._predict_optimal_direction(x, eval_func)
        return self.weight * optimal_direction

    def _check_convergence(self, context: OptimizationContext) -> bool:
        if len(self.convergence_history) < self.history_window:
            return False

        recent_improvements = self.convergence_history[-self.history_window :]
        avg_improvement = np.mean(recent_improvements)
        return avg_improvement < self.convergence_threshold

    def _predict_optimal_direction(self, x: np.ndarray, eval_func: Callable[[np.ndarray], float]) -> float:
        if len(self.predictor.X_observed) < 10:
            return 0.0

        epsilon = 1e-4
        direction_score = 0.0

        for i in range(len(x)):
            x_plus = x.copy()
            x_plus[i] += epsilon
            try:
                y_plus = eval_func(x_plus)
            except Exception:
                y_plus = float("inf")

            x_minus = x.copy()
            x_minus[i] -= epsilon
            try:
                y_minus = eval_func(x_minus)
            except Exception:
                y_minus = float("inf")

            gradient_i = (y_plus - y_minus) / (2 * epsilon)
            direction_score -= abs(gradient_i)

        return max(0, direction_score)


def create_bayesian_guidance_bias(**kwargs) -> BayesianGuidanceBias:
    """Create a BayesianGuidanceBias."""
    return BayesianGuidanceBias(**kwargs)


def create_bayesian_exploration_bias(**kwargs) -> BayesianExplorationBias:
    """Create a BayesianExplorationBias."""
    return BayesianExplorationBias(**kwargs)


def create_bayesian_convergence_bias(**kwargs) -> BayesianConvergenceBias:
    """Create a BayesianConvergenceBias."""
    return BayesianConvergenceBias(**kwargs)


def create_bayesian_suite() -> List[AlgorithmicBias]:
    """Create a default Bayesian bias suite."""
    return [
        BayesianGuidanceBias(weight=0.2),
        BayesianExplorationBias(weight=0.15, uncertainty_threshold=0.1),
        BayesianConvergenceBias(weight=0.1, convergence_threshold=1e-4),
    ]


__all__ = [
    "BayesianGuidanceBias",
    "BayesianExplorationBias",
    "BayesianConvergenceBias",
    "create_bayesian_guidance_bias",
    "create_bayesian_exploration_bias",
    "create_bayesian_convergence_bias",
    "create_bayesian_suite",
]
