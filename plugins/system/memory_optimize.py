"""Memory optimization plugin."""

from __future__ import annotations

import gc
from typing import Any, Dict

import numpy as np

from ..base import Plugin


class MemoryPlugin(Plugin):
    """Collect memory snapshots and run periodic cleanup."""

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Optimizes solver memory usage and snapshots memory metrics; "
        "mutates solver temp_data/population arrays in-place for cleanup."
    )

    def __init__(self, cleanup_interval: int = 10, enable_auto_gc: bool = True) -> None:
        super().__init__("memory_optimize")
        self.cleanup_interval = int(cleanup_interval)
        self.enable_auto_gc = bool(enable_auto_gc)
        self.memory_snapshots: list[Dict[str, Any]] = []

    def on_solver_init(self, solver) -> None:
        self.memory_snapshots = []
        self._take_memory_snapshot(0)

    def on_population_init(self, population, objectives, violations) -> None:
        self._optimize_arrays(population, objectives, violations)

    def on_generation_start(self, generation: int) -> None:
        return None

    def on_generation_end(self, generation: int) -> None:
        if generation % self.cleanup_interval == 0:
            self._cleanup_memory(generation)
        return None

    def on_solver_finish(self, result: Dict[str, Any]) -> None:
        self._take_memory_snapshot("final")
        result["memory_snapshots"] = self.memory_snapshots
        self._cleanup_memory("final")

    def _cleanup_memory(self, generation: Any) -> None:
        if not self.enable_auto_gc:
            return None

        gc.collect()

        if self.solver is not None:
            if hasattr(self.solver, "temp_data"):
                self.solver.temp_data.clear()

            pop, obj, vio = self.get_population_snapshot(self.solver)
            if pop is not None and len(pop) > 0:
                self._optimize_arrays(pop, obj, vio)
                self.commit_population_snapshot(self.solver, pop, obj, vio)

        self._take_memory_snapshot(generation)
        return None

    def _optimize_arrays(self, population: np.ndarray, objectives: np.ndarray, violations: np.ndarray | None) -> None:
        if np.any(~np.isfinite(population)):
            population[~np.isfinite(population)] = 0

        if np.any(~np.isfinite(objectives)):
            objectives[~np.isfinite(objectives)] = 1e10

        if violations is not None and np.any(~np.isfinite(violations)):
            violations[~np.isfinite(violations)] = 1e10
        return None

    def _take_memory_snapshot(self, generation: Any) -> None:
        try:
            import os
            import psutil

            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            snapshot = {
                "generation": generation,
                "rss_mb": memory_info.rss / 1024 / 1024,
                "vms_mb": memory_info.vms / 1024 / 1024,
            }
            self.memory_snapshots.append(snapshot)
        except ImportError:
            return None
        return None

    def get_memory_usage(self) -> Dict[str, Any]:
        if not self.memory_snapshots:
            return {}

        latest = self.memory_snapshots[-1]
        first = self.memory_snapshots[0]
        return {
            "current_mb": latest["rss_mb"],
            "peak_mb": max(s["rss_mb"] for s in self.memory_snapshots),
            "growth_mb": latest["rss_mb"] - first["rss_mb"],
            "snapshots": self.memory_snapshots,
        }
