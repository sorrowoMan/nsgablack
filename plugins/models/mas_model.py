"""
MAS model plugin: maintains a lightweight surrogate for MASAdapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

from ..base import Plugin
from ...utils.context.context_keys import KEY_MAS_MODEL


@dataclass
class MASModelConfig:
    min_train_samples: int = 20
    retrain_every_call: bool = True
    model_type: str = "rf"
    max_train_samples: int = 5000


class MASModelPlugin(Plugin):
    context_requires = ()
    context_provides = (KEY_MAS_MODEL,)
    context_mutates = (KEY_MAS_MODEL,)
    context_cache = ()
    context_notes = "Consumes adapter/context population snapshot and provides model state for MAS usage."
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
        from ...utils.surrogate.vector_surrogate import VectorSurrogate

        n_obj = int(getattr(solver, "num_objectives", 1) or 1)
        self._surrogate = VectorSurrogate(num_objectives=n_obj, model_type=self.cfg.model_type)
        return None

    def on_generation_end(self, generation: int):
        solver = self.solver
        if solver is None:
            return None
        pop, objs, _ = self.resolve_population_snapshot(solver)
        if objs is None or len(pop) == 0:
            return None

        for i in range(len(pop)):
            self._X.append(np.asarray(pop[i], dtype=float))
            self._Y.append(np.asarray(objs[i], dtype=float))

        max_keep = max(0, int(getattr(self.cfg, "max_train_samples", 0) or 0))
        if max_keep > 0 and len(self._X) > max_keep:
            overflow = len(self._X) - max_keep
            del self._X[:overflow]
            del self._Y[:overflow]

        if len(self._X) >= int(self.cfg.min_train_samples) and bool(self.cfg.retrain_every_call):
            X = np.asarray(self._X, dtype=float)
            Y = np.asarray(self._Y, dtype=float)
            self._surrogate.fit(X, Y)
        return None

    def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if self._surrogate is None:
            return context
        context[KEY_MAS_MODEL] = self._surrogate
        return context

