"""L4 evaluation runtime primitives (single mediation entry)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Protocol, Sequence, Tuple

import numpy as np


class EvaluationProvider(Protocol):
    name: str
    semantic_mode: str  # exact | equivalent | approximate

    def can_handle_individual(self, solver: Any, x: np.ndarray, context: Mapping[str, Any]) -> bool:
        ...

    def evaluate_individual(
        self,
        solver: Any,
        x: np.ndarray,
        context: Mapping[str, Any],
        individual_id: Optional[int] = None,
    ) -> Optional[Tuple[np.ndarray, float]]:
        ...

    def can_handle_population(self, solver: Any, population: np.ndarray, context: Mapping[str, Any]) -> bool:
        ...

    def evaluate_population(
        self,
        solver: Any,
        population: np.ndarray,
        context: Mapping[str, Any],
    ) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        ...


@dataclass(frozen=True)
class EvaluationMediatorConfig:
    allow_approximate: bool = False
    strict_conflict: bool = True


class EvaluationMediator:
    """Single entrypoint for evaluation providers."""

    def __init__(self, config: Optional[EvaluationMediatorConfig] = None) -> None:
        self.config = config or EvaluationMediatorConfig()
        self._providers: list[EvaluationProvider] = []

    def register_provider(self, provider: EvaluationProvider) -> None:
        name = str(getattr(provider, "name", provider.__class__.__name__))
        if any(str(getattr(p, "name", p.__class__.__name__)) == name for p in self._providers):
            raise ValueError(f"Evaluation provider '{name}' already registered")
        mode = str(getattr(provider, "semantic_mode", "approximate")).strip().lower()
        if mode not in {"exact", "equivalent", "approximate"}:
            raise ValueError(f"Evaluation provider '{name}' has invalid semantic_mode='{mode}'")
        self._providers.append(provider)

    def list_providers(self) -> Tuple[EvaluationProvider, ...]:
        return tuple(self._providers)

    def evaluate_individual(
        self,
        solver: Any,
        x: np.ndarray,
        *,
        individual_id: Optional[int] = None,
        context: Optional[Mapping[str, Any]] = None,
        fallback: Callable[[], Tuple[np.ndarray, float]],
    ) -> Tuple[np.ndarray, float]:
        ctx = dict(context or {})
        candidates: list[EvaluationProvider] = []
        for p in self._providers:
            can_fn = getattr(p, "can_handle_individual", None)
            if not callable(can_fn):
                continue
            try:
                if bool(can_fn(solver, x, ctx)):
                    candidates.append(p)
            except Exception:
                continue

        if not candidates:
            return fallback()

        if len(candidates) > 1 and bool(self.config.strict_conflict):
            names = ", ".join(str(getattr(x, "name", x.__class__.__name__)) for x in candidates)
            raise RuntimeError(f"Multiple evaluation providers can handle individual: {names}")

        chosen = candidates[0]
        mode = str(getattr(chosen, "semantic_mode", "approximate")).strip().lower()
        if mode == "approximate" and not bool(self.config.allow_approximate):
            return fallback()

        eval_fn = getattr(chosen, "evaluate_individual", None)
        if not callable(eval_fn):
            return fallback()
        out = eval_fn(solver, x, ctx, individual_id=individual_id)
        if out is None:
            return fallback()
        return out

    def evaluate_population(
        self,
        solver: Any,
        population: np.ndarray,
        *,
        context: Optional[Mapping[str, Any]] = None,
        fallback: Callable[[], Tuple[np.ndarray, np.ndarray]],
    ) -> Tuple[np.ndarray, np.ndarray]:
        ctx = dict(context or {})
        candidates: list[EvaluationProvider] = []
        for p in self._providers:
            try:
                if bool(p.can_handle_population(solver, population, ctx)):
                    candidates.append(p)
            except Exception:
                continue

        if not candidates:
            return fallback()

        if len(candidates) > 1 and bool(self.config.strict_conflict):
            names = ", ".join(str(getattr(x, "name", x.__class__.__name__)) for x in candidates)
            raise RuntimeError(f"Multiple evaluation providers can handle population: {names}")

        chosen = candidates[0]
        mode = str(getattr(chosen, "semantic_mode", "approximate")).strip().lower()
        if mode == "approximate" and not bool(self.config.allow_approximate):
            return fallback()

        out = chosen.evaluate_population(solver, population, ctx)
        if out is None:
            return fallback()
        return out
