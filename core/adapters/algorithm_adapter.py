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

    def __init__(self, name: str, priority: int = 0) -> None:
        self.name = name
        self.priority = priority

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


class CompositeAdapter(AlgorithmAdapter):
    """Combine multiple adapters and merge their proposals."""

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
            proposed = list(adapter.propose(solver, context) or [])
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
