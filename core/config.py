"""Core configuration schema (stable).

This module intentionally contains only lightweight dataclasses and should not
import optional heavy dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np


@dataclass
class SolverConfig:
    """Configuration class for solvers."""

    # Basic parameters
    max_generations: int = 100
    pop_size: int = 100
    random_seed: Optional[int] = None

    # Algorithm-specific parameters
    crossover_rate: float = 0.9
    mutation_rate: float = 0.1
    selection_pressure: float = 2.0

    # Performance parameters
    evaluation_budget: Optional[int] = None
    time_limit: Optional[float] = None
    parallel: bool = False
    n_workers: int = 1

    # Output parameters
    verbose: bool = False
    save_history: bool = True
    convergence_tolerance: float = 1e-6
    stagnation_generations: int = 20


@dataclass
class StorageConfig:
    """Aggregated storage/checkpoint configuration for SolverBase.

    Pass a single ``StorageConfig`` instead of the individual
    ``context_store_*`` / ``snapshot_store_*`` keyword arguments.
    The flat kwargs remain supported for backward compatibility; if both
    are supplied, ``StorageConfig`` takes precedence field-by-field.

    Example::

        cfg = StorageConfig(
            context_store_backend="redis",
            snapshot_store_backend="file",
            snapshot_store_dir="/tmp/runs",
        )
        solver = ComposableSolver(problem=p, storage_config=cfg)
    """

    # --- ContextStore ---
    context_store_backend: str = "memory"
    context_store_ttl_seconds: Optional[float] = None
    context_store_redis_url: str = "redis://localhost:6379/0"
    context_store_key_prefix: str = "nsgablack:context"

    # --- SnapshotStore ---
    snapshot_store_backend: str = "memory"
    snapshot_store_ttl_seconds: Optional[float] = None
    snapshot_store_redis_url: str = "redis://localhost:6379/0"
    snapshot_store_key_prefix: str = "nsgablack:snapshot"
    snapshot_store_dir: Optional[str] = None
    snapshot_store_serializer: str = "safe"
    snapshot_store_hmac_env_var: str = "NSGABLACK_SNAPSHOT_HMAC_KEY"
    snapshot_store_unsafe_allow_unsigned: bool = False
    snapshot_store_max_payload_bytes: int = 8_388_608
    snapshot_schema: str = "population_snapshot_v1"


def _apply_storage_config(
    storage_config: Optional["StorageConfig"],
    kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge StorageConfig fields into a flat kwargs dict.

    Fields present in *storage_config* win over same-named keys already in
    *kwargs*.  Returns a new dict (does not mutate the input).
    """
    if storage_config is None:
        return dict(kwargs)
    merged = dict(kwargs)
    for field_name in StorageConfig.__dataclass_fields__:  # type: ignore[attr-defined]
        merged[field_name] = getattr(storage_config, field_name)
    return merged


@dataclass
class OptimizationResult:
    """Standard result structure for all solvers."""

    pareto_solutions: np.ndarray
    pareto_objectives: np.ndarray

    generations: int
    evaluations: int
    elapsed_time: float
    converged: bool

    history: Optional[Dict[str, Any]] = None
    convergence_data: Optional[Dict[str, Any]] = None
    solver_info: Optional[Dict[str, Any]] = None

    hypervolume: Optional[float] = None
    diversity_metric: Optional[float] = None
    convergence_metric: Optional[float] = None


__all__ = [
    "SolverConfig",
    "StorageConfig",
    "_apply_storage_config",
    "OptimizationResult",
]

