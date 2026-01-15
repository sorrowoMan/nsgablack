"""Unified surrogate interface for single NSGA-II workflows."""
from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple
import numpy as np

try:
    from ..core.base import BlackBoxProblem
    from ..core.solver import BlackBoxSolverNSGAII
    from ..surrogate import SurrogateManager
except Exception:
    try:
        from core.base import BlackBoxProblem
        from core.solver import BlackBoxSolverNSGAII
        from surrogate import SurrogateManager
    except Exception:  # pragma: no cover - import fallback
        BlackBoxProblem = None
        BlackBoxSolverNSGAII = object
        SurrogateManager = None
try:
    from ..bias.surrogate.base import SurrogateBiasContext
except Exception:
    try:
        from bias.surrogate.base import SurrogateBiasContext
    except Exception:  # pragma: no cover - optional
        SurrogateBiasContext = None


class SurrogateUnifiedNSGAII(BlackBoxSolverNSGAII):
    """NSGA-II with unified surrogate usage: prefilter, score-bias, or surrogate eval."""

    _DEFAULT_PREFILTER = {
        'enabled': False,
        'ratio': 0.3,
        'min_real': 5,
        'max_real': None,
        'strategy': 'best',
        'objective_weights': None,
        'uncertainty_weight': 0.3,
    }
    _DEFAULT_SCORE_BIAS = {
        'enabled': False,
        'weight': 0.1,
        'sign': -1.0,
        'mode': 'vector',
        'objective_weights': None,
        'apply_to': 'real',
        'normalize': False,
    }
    _DEFAULT_SURROGATE_EVAL = {
        'enabled': False,
        'ratio': 1.0,
        'min_real': 0,
        'strategy': 'random',
        'objective_weights': None,
        'uncertainty_weight': 0.0,
    }
    _DEFAULT_CONSTRAINTS = {
        'evaluation': 'real_only',
    }

    def __init__(
        self,
        problem: BlackBoxProblem,
        surrogate_manager: Optional[SurrogateManager] = None,
        surrogate_config: Optional[Dict] = None,
        prefilter: Optional[Dict] = None,
        score_bias: Optional[Dict] = None,
        surrogate_eval: Optional[Dict] = None,
        constraint_eval: Optional[Dict] = None,
        surrogate_biases: Optional[Sequence] = None,
        min_training_samples: int = 10,
        auto_update: bool = True,
        update_interval: int = 1,
    ):
        super().__init__(problem)
        self.surrogate_manager = surrogate_manager or SurrogateManager(problem, **(surrogate_config or {}))
        self.surrogate_prefilter = self._normalize_config(prefilter, self._DEFAULT_PREFILTER)
        self.surrogate_score_bias = self._normalize_config(score_bias, self._DEFAULT_SCORE_BIAS)
        self.surrogate_eval = self._normalize_config(surrogate_eval, self._DEFAULT_SURROGATE_EVAL)
        self.surrogate_constraints = self._normalize_config(constraint_eval, self._DEFAULT_CONSTRAINTS, use_enabled=False)
        self.surrogate_biases = list(surrogate_biases) if surrogate_biases else []
        self._surrogate_bias_last_gen = None
        self.surrogate_min_samples = max(0, int(min_training_samples))
        self.surrogate_auto_update = bool(auto_update)
        self.surrogate_update_interval = max(1, int(update_interval))
        self.surrogate_eval_count = 0
        self.real_eval_count = 0

    def configure_surrogate(
        self,
        prefilter: Optional[Dict] = None,
        score_bias: Optional[Dict] = None,
        surrogate_eval: Optional[Dict] = None,
        constraint_eval: Optional[Dict] = None,
    ) -> None:
        """Update surrogate usage configs at runtime."""
        if prefilter is not None:
            self.surrogate_prefilter = self._normalize_config(prefilter, self._DEFAULT_PREFILTER)
        if score_bias is not None:
            self.surrogate_score_bias = self._normalize_config(score_bias, self._DEFAULT_SCORE_BIAS)
        if surrogate_eval is not None:
            self.surrogate_eval = self._normalize_config(surrogate_eval, self._DEFAULT_SURROGATE_EVAL)
        if constraint_eval is not None:
            self.surrogate_constraints = self._normalize_config(
                constraint_eval,
                self._DEFAULT_CONSTRAINTS,
                use_enabled=False
            )

    def evaluate_population(self, population):  # noqa: D401 - keep signature aligned
        population = np.asarray(population, dtype=float)
        n = population.shape[0]

        self._maybe_apply_surrogate_biases(population)

        use_prefilter = self.surrogate_prefilter.get('enabled', False)
        use_score_bias = self.surrogate_score_bias.get('enabled', False)
        use_surrogate_eval = self.surrogate_eval.get('enabled', False)

        surrogate_ready = self._surrogate_ready()
        if not surrogate_ready:
            use_prefilter = False
            use_score_bias = False
            use_surrogate_eval = False

        if not (use_prefilter or use_score_bias or use_surrogate_eval):
            return super().evaluate_population(population)

        predictions = self._predict_population(population) if surrogate_ready else None
        real_mask = np.ones(n, dtype=bool)

        if use_prefilter:
            real_mask = self._select_real_mask_prefilter(population, predictions)
        elif use_surrogate_eval:
            real_mask = self._select_real_mask_surrogate(population, predictions)

        objectives = np.zeros((n, self.num_objectives), dtype=float)
        violations = np.zeros(n, dtype=float)

        real_indices = np.where(real_mask)[0]
        for idx in real_indices:
            obj, vio = self._evaluate_individual(population[idx], individual_id=int(idx))
            objectives[idx] = self._format_objective_vector(obj)
            violations[idx] = float(vio)

        surrogate_indices = np.where(~real_mask)[0]
        if surrogate_indices.size > 0:
            if predictions is None:
                predictions = self._predict_population(population)
            objectives[surrogate_indices] = predictions[surrogate_indices]
            violations[surrogate_indices] = self._estimate_surrogate_violations(population[surrogate_indices])

        if real_indices.size > 0 and self.surrogate_manager is not None:
            self._add_training_batch(population[real_indices], objectives[real_indices])
            self.real_eval_count += int(real_indices.size)
            self.evaluation_count += int(real_indices.size)

        if surrogate_indices.size > 0:
            self.surrogate_eval_count += int(surrogate_indices.size)

        if use_score_bias and predictions is not None:
            objectives = self._apply_score_bias(objectives, predictions, real_mask)

        self._maybe_update_surrogate()
        return objectives, violations

    def _maybe_apply_surrogate_biases(self, population: np.ndarray) -> None:
        if not self.surrogate_biases:
            return
        if self._surrogate_bias_last_gen == self.generation:
            return
        context = self._build_surrogate_bias_context(population)
        for bias in self.surrogate_biases:
            updates = self._call_surrogate_bias(bias, context)
            self._apply_surrogate_updates(updates)
        self._surrogate_bias_last_gen = self.generation

    def _build_surrogate_bias_context(self, population: np.ndarray):
        status = {}
        n_training = 0
        model_quality = {}
        if self.surrogate_manager is not None:
            try:
                status = self.surrogate_manager.get_status()
            except Exception:
                status = {}
            n_training = int(status.get('n_training_samples', 0) or 0)
            model_quality = status.get('model_quality', {}) or {}
        payload = {
            'generation': self.generation,
            'max_generations': self.max_generations,
            'population': population,
            'surrogate_manager': self.surrogate_manager,
            'surrogate_ready': self._surrogate_ready(),
            'n_training_samples': n_training,
            'model_quality': model_quality,
            'real_eval_count': self.real_eval_count,
            'surrogate_eval_count': self.surrogate_eval_count,
            'prefilter': dict(self.surrogate_prefilter),
            'score_bias': dict(self.surrogate_score_bias),
            'surrogate_eval': dict(self.surrogate_eval),
            'constraint_eval': dict(self.surrogate_constraints),
            'extras': {'status': status},
        }
        if SurrogateBiasContext is None:
            return payload
        try:
            return SurrogateBiasContext(**payload)
        except Exception:
            return payload

    def _call_surrogate_bias(self, bias, context) -> Dict:
        if bias is None:
            return {}
        if hasattr(bias, 'should_apply'):
            try:
                if not bias.should_apply(context):
                    return {}
            except Exception:
                pass
        for handler in ('apply', 'compute'):
            if hasattr(bias, handler):
                func = getattr(bias, handler)
                try:
                    result = func(context)
                    return result if isinstance(result, dict) else {}
                except Exception:
                    continue
        if callable(bias):
            try:
                result = bias(context)
                return result if isinstance(result, dict) else {}
            except Exception:
                return {}
        return {}

    def _apply_surrogate_updates(self, updates: Optional[Dict]) -> None:
        if not updates or not isinstance(updates, dict):
            return
        if 'prefilter' in updates:
            self._merge_config(self.surrogate_prefilter, updates.get('prefilter'))
        if 'score_bias' in updates:
            self._merge_config(self.surrogate_score_bias, updates.get('score_bias'))
        if 'surrogate_eval' in updates:
            self._merge_config(self.surrogate_eval, updates.get('surrogate_eval'))
        if 'constraint_eval' in updates:
            self._merge_config(self.surrogate_constraints, updates.get('constraint_eval'))
        if 'min_training_samples' in updates:
            try:
                self.surrogate_min_samples = max(0, int(updates['min_training_samples']))
            except Exception:
                pass
        if 'auto_update' in updates:
            self.surrogate_auto_update = bool(updates['auto_update'])
        if 'update_interval' in updates:
            try:
                self.surrogate_update_interval = max(1, int(updates['update_interval']))
            except Exception:
                pass

    def _merge_config(self, target: Dict, update) -> None:
        if update is None:
            return
        if isinstance(update, dict):
            target.update(update)
            return
        if isinstance(update, bool):
            target['enabled'] = bool(update)

    def _normalize_config(self, config: Optional[Dict], defaults: Dict, use_enabled: bool = True) -> Dict:
        data = defaults.copy()
        if config is None:
            return data
        if isinstance(config, bool):
            if use_enabled:
                data['enabled'] = bool(config)
            return data
        if isinstance(config, dict):
            data.update(config)
            if use_enabled and 'enabled' not in data:
                data['enabled'] = True
        return data

    def _surrogate_ready(self) -> bool:
        if self.surrogate_manager is None:
            return False
        model = getattr(self.surrogate_manager, 'surrogate_model', None)
        if model is None:
            return False
        if hasattr(model, 'X_train'):
            try:
                if len(model.X_train) >= self.surrogate_min_samples:
                    return True
            except Exception:
                pass
        return bool(getattr(model, 'is_trained', False))

    def _predict_population(self, population: np.ndarray) -> np.ndarray:
        if self.surrogate_manager is None:
            raise RuntimeError("Surrogate manager is not available")
        preds = self.surrogate_manager.predict(population)
        return self._format_objective_matrix(preds, population.shape[0])

    def _format_objective_vector(self, obj) -> np.ndarray:
        arr = np.asarray(obj, dtype=float).flatten()
        if arr.size == 0:
            return np.zeros(self.num_objectives, dtype=float)
        if arr.size == 1 and self.num_objectives > 1:
            return np.repeat(arr[0], self.num_objectives)
        if arr.size >= self.num_objectives:
            return arr[: self.num_objectives]
        out = np.zeros(self.num_objectives, dtype=float)
        out[: arr.size] = arr
        return out

    def _format_objective_matrix(self, values, n_samples: int) -> np.ndarray:
        arr = np.asarray(values, dtype=float)
        if arr.ndim == 0:
            arr = np.full((n_samples, 1), float(arr))
        elif arr.ndim == 1:
            if arr.size == n_samples:
                arr = arr.reshape(n_samples, 1)
            elif arr.size == self.num_objectives:
                arr = np.repeat(arr.reshape(1, -1), n_samples, axis=0)
            else:
                arr = arr.reshape(n_samples, 1)
        if arr.shape[1] == 1 and self.num_objectives > 1:
            arr = np.repeat(arr, self.num_objectives, axis=1)
        elif arr.shape[1] > self.num_objectives:
            arr = arr[:, : self.num_objectives]
        elif arr.shape[1] < self.num_objectives:
            pad = np.zeros((n_samples, self.num_objectives - arr.shape[1]), dtype=float)
            arr = np.hstack([arr, pad])
        return arr

    def _select_real_mask_prefilter(self, population: np.ndarray, predictions: np.ndarray) -> np.ndarray:
        cfg = self.surrogate_prefilter
        n = population.shape[0]
        n_real = self._resolve_real_count(n, cfg.get('ratio', 0.0), cfg.get('min_real', 0), cfg.get('max_real'))
        return self._select_mask_by_strategy(population, n, n_real, predictions, cfg)

    def _select_real_mask_surrogate(self, population: np.ndarray, predictions: np.ndarray) -> np.ndarray:
        cfg = self.surrogate_eval
        n = population.shape[0]
        surrogate_ratio = float(cfg.get('ratio', 1.0))
        surrogate_ratio = float(np.clip(surrogate_ratio, 0.0, 1.0))
        n_real = n - int(round(surrogate_ratio * n))
        n_real = max(int(cfg.get('min_real', 0)), n_real)
        n_real = min(n_real, n)
        return self._select_mask_by_strategy(population, n, n_real, predictions, cfg)

    def _resolve_real_count(self, n: int, ratio: float, min_real: int, max_real: Optional[int]) -> int:
        ratio = float(np.clip(ratio, 0.0, 1.0))
        n_real = int(round(ratio * n))
        n_real = max(int(min_real), n_real)
        if max_real is not None:
            n_real = min(int(max_real), n_real)
        return max(0, min(n_real, n))

    def _select_mask_by_strategy(
        self,
        population: np.ndarray,
        n: int,
        n_real: int,
        predictions: Optional[np.ndarray],
        cfg: Dict,
    ) -> np.ndarray:
        mask = np.zeros(n, dtype=bool)
        if n_real <= 0:
            return mask
        if n_real >= n:
            mask[:] = True
            return mask

        strategy = str(cfg.get('strategy', 'best')).lower()
        if strategy == 'random' or predictions is None:
            indices = np.random.choice(n, n_real, replace=False)
        else:
            pred_scalar = self._prediction_scalar(predictions, cfg.get('objective_weights'))
            if strategy == 'uncertainty':
                uncertainty = self._uncertainty_scalar(population)
                indices = np.argsort(uncertainty)[-n_real:]
            elif strategy == 'hybrid':
                uncertainty = self._uncertainty_scalar(population)
                weight = float(cfg.get('uncertainty_weight', 0.0))
                score = -pred_scalar + weight * uncertainty
                indices = np.argsort(score)[-n_real:]
            else:
                indices = np.argsort(pred_scalar)[:n_real]

        mask[indices] = True
        return mask

    def _prediction_scalar(self, predictions: np.ndarray, weights: Optional[Sequence[float]]) -> np.ndarray:
        preds = np.asarray(predictions, dtype=float)
        if preds.ndim == 1:
            preds = preds.reshape(-1, 1)
        if preds.shape[1] == 1:
            return preds[:, 0]
        if weights is None:
            return np.mean(preds, axis=1)
        w = np.asarray(weights, dtype=float).flatten()
        if w.size != preds.shape[1]:
            w = np.ones(preds.shape[1], dtype=float)
        w_sum = np.sum(w)
        if w_sum <= 0:
            w = np.ones(preds.shape[1], dtype=float)
            w_sum = float(preds.shape[1])
        w = w / w_sum
        return np.sum(preds * w, axis=1)

    def _uncertainty_scalar(self, population: np.ndarray) -> np.ndarray:
        if self.surrogate_manager is None:
            return np.zeros(population.shape[0], dtype=float)
        try:
            uncertainty = self.surrogate_manager.get_uncertainty(population)
            unc = np.asarray(uncertainty, dtype=float)
            if unc.ndim == 1:
                return unc
            return np.mean(unc, axis=1)
        except Exception:
            return np.zeros(population.shape[0], dtype=float)

    def _estimate_surrogate_violations(self, population: np.ndarray) -> np.ndarray:
        mode = str(self.surrogate_constraints.get('evaluation', 'real_only')).lower()
        if mode == 'skip' or mode == 'real_only':
            return np.zeros(population.shape[0], dtype=float)
        violations = np.zeros(population.shape[0], dtype=float)
        for i in range(population.shape[0]):
            violations[i] = self._constraint_violation(population[i])
        return violations

    def _constraint_violation(self, x: np.ndarray) -> float:
        try:
            cons = self.problem.evaluate_constraints(x)
            cons_arr = np.asarray(cons, dtype=float).flatten()
            if cons_arr.size == 0:
                return 0.0
            return float(np.sum(np.maximum(cons_arr, 0.0)))
        except Exception:
            return 0.0

    def _add_training_batch(self, X: np.ndarray, y: np.ndarray) -> None:
        if self.surrogate_manager is None:
            return
        X_arr = np.asarray(X, dtype=float)
        y_arr = self._format_objective_matrix(y, X_arr.shape[0])
        try:
            self.surrogate_manager.add_training_data(X_arr, y_arr)
        except Exception:
            pass

    def _apply_score_bias(
        self,
        objectives: np.ndarray,
        predictions: np.ndarray,
        real_mask: np.ndarray,
    ) -> np.ndarray:
        cfg = self.surrogate_score_bias
        apply_to = str(cfg.get('apply_to', 'real')).lower()
        if apply_to == 'real':
            mask = real_mask
        elif apply_to == 'surrogate':
            mask = ~real_mask
        else:
            mask = np.ones_like(real_mask, dtype=bool)

        if not np.any(mask):
            return objectives

        preds = self._format_objective_matrix(predictions, objectives.shape[0])
        if cfg.get('normalize', False):
            preds = self._normalize_predictions(preds)
        bias = self._score_bias_vector(preds, cfg)

        out = objectives.copy()
        out[mask] = out[mask] + bias[mask]
        return out

    def _score_bias_vector(self, preds: np.ndarray, cfg: Dict) -> np.ndarray:
        weight = float(cfg.get('weight', 0.0))
        sign = float(cfg.get('sign', -1.0))
        mode = str(cfg.get('mode', 'vector')).lower()
        if mode == 'scalar':
            scalar = self._prediction_scalar(preds, cfg.get('objective_weights'))
            bias = sign * weight * scalar.reshape(-1, 1)
            return np.repeat(bias, self.num_objectives, axis=1)
        return sign * weight * preds

    def _normalize_predictions(self, preds: np.ndarray) -> np.ndarray:
        mins = np.min(preds, axis=0)
        maxs = np.max(preds, axis=0)
        denom = np.where(maxs - mins <= 1e-12, 1.0, maxs - mins)
        return (preds - mins) / denom

    def _maybe_update_surrogate(self) -> None:
        if self.surrogate_manager is None or not self.surrogate_auto_update:
            return
        if self.generation % self.surrogate_update_interval != 0:
            return
        try:
            self.surrogate_manager.update_surrogate()
        except Exception:
            pass
