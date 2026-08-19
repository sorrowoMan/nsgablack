"""Optimization-facing facade over the shared blackbase pipeline orchestrator.

Execution modes, branch isolation, merge semantics, and L0 concurrency limits
belong to :mod:`blackbase.kernel`.  This module only preserves nsgablack's
``mutate``/``repair`` representation surface.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from blackbase.kernel import OrchestrationPolicy
from blackbase.kernel import PipelineOrchestrator as SharedPipelineOrchestrator

from .base import RepresentationComponentContract
from blackbase.context.context_keys import KEY_GENERATION, KEY_PHASE, KEY_STRATEGY_ID, KEY_VNS_K


class PipelineOrchestrator(RepresentationComponentContract):
    """Thin representation adapter around ``blackbase.kernel`` orchestration."""

    context_key: str = KEY_PHASE
    k_key: str = KEY_VNS_K
    selector_key: str = KEY_STRATEGY_ID

    context_requires = (KEY_VNS_K, KEY_STRATEGY_ID, KEY_PHASE, KEY_GENERATION)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    phase_in = (KEY_PHASE,)
    context_notes = (
        "Optimization representation facade; execution semantics are owned by blackbase.kernel.",
    )

    def __init__(
        self,
        *,
        mutate_policy: Optional[OrchestrationPolicy] = None,
        repair_policy: Optional[OrchestrationPolicy] = None,
        mutator: Optional[Any] = None,
        repair_operator: Optional[Any] = None,
        strict: bool = True,
        executor: Any = None,
        pool_scheduler: Any = None,
    ) -> None:
        self.mutate_policy = mutate_policy
        self.repair_policy = repair_policy
        self.mutator = mutator
        self.repair_operator = repair_operator
        self.strict = bool(strict)
        self._shared = SharedPipelineOrchestrator(
            strict=self.strict,
            executor=executor,
            pool_scheduler=pool_scheduler,
        )

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        out = self._run_policy(
            self.mutate_policy,
            x,
            context,
            method="mutate",
            fallback=self.mutator,
        )
        return np.asarray(out, dtype=float)

    def repair(self, x: Any, context: Optional[dict] = None) -> Any:
        return self._run_policy(
            self.repair_policy,
            x,
            context,
            method="repair",
            fallback=self.repair_operator,
        )

    def _run_policy(
        self,
        policy: Optional[OrchestrationPolicy],
        x: Any,
        context: Optional[dict],
        *,
        method: str,
        fallback: Optional[Any],
    ) -> Any:
        if policy is None:
            if fallback is None:
                return x
            return self._shared.call_operator(fallback, x, context, method)
        return self._shared.run_policy(
            policy,
            x,
            context,
            method=method,
            fallback=x,
        )


__all__ = ["OrchestrationPolicy", "PipelineOrchestrator"]
