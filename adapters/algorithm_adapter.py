"""
Algorithm adapter interface for composable solvers.

Adapters provide candidate proposals and consume evaluation feedback.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np


class AlgorithmAdapter(ABC):
    """Base adapter for integrating arbitrary optimization logic."""

    # Optional context contract (class-level defaults)
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = None

    def __init__(self, name: str, priority: int = 0) -> None:
        self.name = name
        self.priority = priority

    def create_local_rng(self, solver: Any = None, seed: Optional[int] = None) -> np.random.Generator:
        """Create a component-local RNG.

        Priority:
        1) explicit seed
        2) solver.fork_rng() if available
        3) independent default RNG
        """
        if seed is not None:
            return np.random.default_rng(int(seed))
        if solver is not None:
            fork = getattr(solver, "fork_rng", None)
            if callable(fork):
                try:
                    rng = fork(self.name)
                    if isinstance(rng, np.random.Generator):
                        return rng
                except Exception:
                    pass
        return np.random.default_rng()

    def setup(self, solver: Any) -> None:
        """Called once before run()."""
        return None

    @abstractmethod
    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        """Return a list of candidate solutions."""
        raise NotImplementedError

    def update(
        self,
        solver: Any,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> None:
        """Consume evaluation feedback for candidates."""
        return None

    def teardown(self, solver: Any) -> None:
        """Called once after run()."""
        return None

    def get_state(self) -> Dict[str, Any]:
        """Return serializable adapter state."""
        return {}

    def set_state(self, state: Dict[str, Any]) -> None:
        """Restore adapter state."""
        return None

    @staticmethod
    def validate_population_snapshot(
        population: np.ndarray,
        objectives: np.ndarray,
        violations: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Normalize and validate population snapshot payload.

        Contract:
        - population: (N, D) float
        - objectives: (N, M) float
        - violations: (N,) float
        """
        pop = np.asarray(population, dtype=float)
        obj = np.asarray(objectives, dtype=float)
        vio = np.asarray(violations, dtype=float).reshape(-1)

        if pop.ndim == 1:
            pop = pop.reshape(1, -1) if pop.size > 0 else pop.reshape(0, 0)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1) if obj.size > 0 else obj.reshape(0, 0)

        n = int(pop.shape[0]) if pop.ndim >= 2 else 0
        if obj.shape[0] != n or vio.shape[0] != n:
            raise ValueError(
                "Population snapshot shape mismatch: "
                f"population={tuple(pop.shape)}, objectives={tuple(obj.shape)}, violations={tuple(vio.shape)}"
            )
        return pop, obj, vio

    def set_population(self, population: np.ndarray, objectives: np.ndarray, violations: np.ndarray) -> bool:
        """Optional population write-back contract for runtime plugins.

        Adapters that own population/objective state should override this and
        return True when write-back succeeds. Default returns False (unsupported).
        """
        _ = self.validate_population_snapshot(population, objectives, violations)
        return False

    @staticmethod
    def coerce_candidates(value: Any) -> List[Any]:
        """Normalize propose() output without relying on ambiguous truthiness."""
        if value is None:
            return []
        if isinstance(value, np.ndarray):
            if value.ndim <= 1:
                return [value]
            return [np.asarray(row) for row in value]
        return list(value)

    def get_context_contract(self) -> Dict[str, Any]:
        requires = list(getattr(self, "context_requires", ()) or ())
        provides = list(getattr(self, "context_provides", ()) or ())
        mutates = list(getattr(self, "context_mutates", ()) or ())
        cache = list(getattr(self, "context_cache", ()) or ())

        # Backward compatibility: legacy adapter declarations.
        requires.extend(list(getattr(self, "requires_context_keys", ()) or ()))
        requires.extend(list(getattr(self, "runtime_requires", ()) or ()))
        provides.extend(list(getattr(self, "provides_context_keys", ()) or ()))
        provides.extend(list(getattr(self, "runtime_provides", ()) or ()))
        mutates.extend(list(getattr(self, "mutates_context_keys", ()) or ()))
        mutates.extend(list(getattr(self, "runtime_mutates", ()) or ()))
        cache.extend(list(getattr(self, "cache_context_keys", ()) or ()))
        cache.extend(list(getattr(self, "runtime_cache", ()) or ()))

        notes_parts: List[str] = []
        for attr in ("context_notes", "recommended_mutators", "recommended_plugins", "companions", "recommended_suite"):
            value = getattr(self, attr, None)
            if value is None:
                continue
            if isinstance(value, str):
                text = value.strip()
                if text:
                    notes_parts.append(text)
                continue
            if isinstance(value, Iterable):
                items = [str(x).strip() for x in value if str(x).strip()]
                if items:
                    notes_parts.append(f"{attr}=" + ", ".join(items))
                continue
            text = str(value).strip()
            if text:
                notes_parts.append(f"{attr}={text}")

        return {
            "requires": requires,
            "provides": provides,
            "mutates": mutates,
            "cache": cache,
            "notes": " | ".join(notes_parts) if notes_parts else None,
        }

    def get_runtime_context_projection(self, solver: Any) -> Dict[str, Any]:
        """Return best-effort runtime fields to expose in solver.get_context()."""
        return {}

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        """Return writer attribution for projected runtime context fields."""
        _ = solver
        return {}


class CompositeAdapter(AlgorithmAdapter):
    """Combine multiple adapters and merge their proposals."""
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Composite adapter: unions child adapter contracts."

    def __init__(self, adapters: Sequence[AlgorithmAdapter], name: str = "composite", priority: int = 0) -> None:
        super().__init__(name=name, priority=priority)
        self.adapters = list(adapters)
        self._last_ranges: List[Tuple[AlgorithmAdapter, int, int]] = []

    def setup(self, solver: Any) -> None:
        for adapter in self.adapters:
            adapter.setup(solver)

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        candidates: List[np.ndarray] = []
        self._last_ranges = []
        for adapter in self.adapters:
            start = len(candidates)
            proposed = self.coerce_candidates(adapter.propose(solver, context))
            candidates.extend(proposed)
            end = len(candidates)
            self._last_ranges.append((adapter, start, end))
        return candidates

    def update(
        self,
        solver: Any,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> None:
        if not self._last_ranges:
            for adapter in self.adapters:
                adapter.update(solver, candidates, objectives, violations, context)
            return
        for adapter, start, end in self._last_ranges:
            if start == end:
                continue
            adapter.update(
                solver,
                candidates[start:end],
                objectives[start:end],
                violations[start:end],
                context,
            )

    def teardown(self, solver: Any) -> None:
        for adapter in self.adapters:
            adapter.teardown(solver)

    def get_state(self) -> Dict[str, Any]:
        return {adapter.name: adapter.get_state() for adapter in self.adapters}

    def set_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        for adapter in self.adapters:
            if adapter.name in state:
                adapter.set_state(state[adapter.name])

    def get_context_contract(self) -> Dict[str, Any]:
        contract = super().get_context_contract()
        requires = list(contract.get("requires", ()) or ())
        provides = list(contract.get("provides", ()) or ())
        mutates = list(contract.get("mutates", ()) or ())
        cache = list(contract.get("cache", ()) or ())
        for adapter in self.adapters:
            sub = adapter.get_context_contract()
            requires.extend(list(sub.get("requires", ()) or ()))
            provides.extend(list(sub.get("provides", ()) or ()))
            mutates.extend(list(sub.get("mutates", ()) or ()))
            cache.extend(list(sub.get("cache", ()) or ()))
        return {
            "requires": requires,
            "provides": provides,
            "mutates": mutates,
            "cache": cache,
            "notes": "composite",
        }
