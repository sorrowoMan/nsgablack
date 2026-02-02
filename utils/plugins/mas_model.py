"""
MAS model plugin: maintains a lightweight surrogate for MASAdapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

from .base import Plugin


@dataclass
class MASModelConfig:
    min_train_samples: int = 20
    retrain_every_call: bool = True
    model_type: str = "rf"


class MASModelPlugin(Plugin):
    """
    Provides a model for MASAdapter via context["mas_model"].
    """

    def __init__(
        self,
        name: str = "mas_model",
        *,
        config: Optional[MASModelConfig] = None,
    ) -> None:
        super().__init__(name=name)
        self.cfg = config or MASModelConfig()
        self._X: list[np.ndarray] = []
        self._Y: list[np.ndarray] = []
        self._surrogate = None

    def on_solver_init(self, solver: Any):
        from ..surrogate.vector_surrogate import VectorSurrogate

        n_obj = int(getattr(solver, "num_objectives", 1) or 1)
        self._surrogate = VectorSurrogate(num_objectives=n_obj, model_type=self.cfg.model_type)
        return None

    def on_generation_end(self, generation: int):
        solver = self.solver
        if solver is None:
            return None
        if getattr(solver, "population", None) is None:
            return None
        pop = np.asarray(solver.population)
        objs = np.asarray(solver.objectives) if getattr(solver, "objectives", None) is not None else None
        if objs is None or len(pop) == 0:
            return None

        for i in range(len(pop)):
            self._X.append(np.asarray(pop[i], dtype=float))
            self._Y.append(np.asarray(objs[i], dtype=float))

        if len(self._X) >= int(self.cfg.min_train_samples) and bool(self.cfg.retrain_every_call):
            X = np.asarray(self._X, dtype=float)
            Y = np.asarray(self._Y, dtype=float)
            self._surrogate.fit(X, Y)
        return None

    def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if self._surrogate is None:
            return context
        context["mas_model"] = self._surrogate
        return context
