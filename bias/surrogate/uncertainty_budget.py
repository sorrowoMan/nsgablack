"""Uncertainty-driven surrogate budget bias."""
from __future__ import annotations

from typing import Any, Dict, Optional
import numpy as np

from .base import SurrogateControlBias


class UncertaintyBudgetBias(SurrogateControlBias):
    """Adjust real-eval budget based on surrogate uncertainty."""
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "No explicit context dependency; outputs scalar bias only."



    def __init__(
        self,
        target: str = "prefilter",
        min_real_ratio: float = 0.1,
        max_real_ratio: float = 0.8,
        uncertainty_low: float = 0.05,
        uncertainty_high: float = 0.2,
        sample_size: int = 32,
        update_interval: int = 1,
        min_real: Optional[int] = None,
        force_real_when_not_ready: bool = True,
        quality_floor: Optional[float] = None,
        name: str = "uncertainty_budget",
    ):
        super().__init__(name=name)
        self.target = str(target).lower()
        self.min_real_ratio = float(min_real_ratio)
        self.max_real_ratio = float(max_real_ratio)
        self.uncertainty_low = float(uncertainty_low)
        self.uncertainty_high = float(uncertainty_high)
        self.sample_size = max(0, int(sample_size))
        self.update_interval = max(1, int(update_interval))
        self.min_real = min_real
        self.force_real_when_not_ready = bool(force_real_when_not_ready)
        self.quality_floor = quality_floor
        self._rng = np.random.default_rng()

    def should_apply(self, context: Any) -> bool:
        generation = getattr(context, "generation", 0)
        return (generation % self.update_interval) == 0

    def apply(self, context: Any) -> Dict[str, Any]:
        if not self.should_apply(context):
            return {}
        if not getattr(context, "surrogate_ready", False):
            return self._fallback_when_not_ready()

        population = getattr(context, "population", None)
        if population is None:
            return {}
        population = np.asarray(population, dtype=float)
        if population.size == 0:
            return {}
        if population.ndim == 1:
            population = population.reshape(1, -1)

        if self.sample_size and population.shape[0] > self.sample_size:
            indices = self._rng.choice(population.shape[0], self.sample_size, replace=False)
            sample = population[indices]
        else:
            sample = population

        surrogate_manager = getattr(context, "surrogate_manager", None)
        if surrogate_manager is None:
            return {}

        try:
            uncertainty = surrogate_manager.get_uncertainty(sample)
        except Exception:
            return {}

        unc_value = self._reduce_uncertainty(uncertainty)
        real_ratio = self._map_uncertainty_to_ratio(unc_value)

        quality_override = self._quality_override(context, real_ratio)
        if quality_override is not None:
            real_ratio = quality_override

        return self._build_update(real_ratio)

    def _fallback_when_not_ready(self) -> Dict[str, Any]:
        if not self.force_real_when_not_ready:
            return {}
        if self.target == "surrogate_eval":
            return {"surrogate_eval": {"enabled": True, "ratio": 0.0}}
        return {"prefilter": {"enabled": True, "ratio": 1.0}}

    def _reduce_uncertainty(self, uncertainty: Any) -> float:
        unc = np.asarray(uncertainty, dtype=float)
        if unc.ndim == 0:
            return float(unc)
        if unc.ndim == 1:
            return float(np.mean(unc))
        return float(np.mean(unc))

    def _map_uncertainty_to_ratio(self, unc_value: float) -> float:
        low = self.uncertainty_low
        high = self.uncertainty_high
        if high <= low:
            return self.max_real_ratio if unc_value >= low else self.min_real_ratio
        ratio = self.min_real_ratio + (unc_value - low) / (high - low) * (
            self.max_real_ratio - self.min_real_ratio
        )
        return float(np.clip(ratio, self.min_real_ratio, self.max_real_ratio))

    def _quality_override(self, context: Any, current_ratio: float) -> Optional[float]:
        if self.quality_floor is None:
            return None
        quality = self._extract_quality(getattr(context, "model_quality", {}))
        if quality is None:
            return None
        if quality < float(self.quality_floor):
            return self.max_real_ratio
        return None

    def _extract_quality(self, model_quality: Dict[str, Any]) -> Optional[float]:
        if not isinstance(model_quality, dict) or not model_quality:
            return None
        if "r2" in model_quality:
            try:
                return float(model_quality["r2"])
            except Exception:
                return None
        r2_values = []
        for key, value in model_quality.items():
            if str(key).startswith("r2"):
                try:
                    r2_values.append(float(value))
                except Exception:
                    continue
        if r2_values:
            return float(np.mean(r2_values))
        return None

    def _build_update(self, real_ratio: float) -> Dict[str, Any]:
        update = {}
        if self.target == "surrogate_eval":
            update["surrogate_eval"] = {"enabled": True, "ratio": 1.0 - real_ratio}
            if self.min_real is not None:
                update["surrogate_eval"]["min_real"] = int(self.min_real)
        else:
            update["prefilter"] = {"enabled": True, "ratio": real_ratio}
            if self.min_real is not None:
                update["prefilter"]["min_real"] = int(self.min_real)
        return update
