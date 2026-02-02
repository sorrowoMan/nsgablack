"""
Representation pipeline for encoding, repair, initialization, and mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, List, Tuple, Iterable
import contextlib
import threading
import numpy as np


class EncodingPlugin(Protocol):
    def encode(self, x: Any, context: Optional[dict] = None) -> Any:
        ...

    def decode(self, x: Any, context: Optional[dict] = None) -> Any:
        ...


class RepairPlugin(Protocol):
    def repair(self, x: Any, context: Optional[dict] = None) -> Any:
        ...


def _parallel_repair_task(args: tuple) -> Any:
    """Top-level helper for process-based repair."""
    inner, x, context = args
    return inner.repair(x, context)


class ParallelRepair:
    """Optional wrapper to run repair_batch in parallel (thread/process).

    Notes:
    - Default backend is "thread" for safety with non-picklable repair objects.
    - "process" requires the repair object to be picklable; otherwise it
      falls back to thread or serial execution.
    """

    def __init__(
        self,
        inner: RepairPlugin,
        *,
        backend: str = "thread",
        max_workers: Optional[int] = None,
        min_batch_size: int = 16,
        chunk_size: Optional[int] = None,
        verbose: bool = False,
    ) -> None:
        self.inner = inner
        self.backend = str(backend or "thread")
        self.max_workers = max_workers
        self.min_batch_size = int(min_batch_size)
        self.chunk_size = chunk_size
        self.verbose = bool(verbose)

    def repair(self, x: Any, context: Optional[dict] = None) -> Any:
        return self.inner.repair(x, context)

    def repair_batch(self, xs: Any, contexts: Optional[Iterable[Optional[dict]]] = None) -> Any:
        if xs is None:
            return xs
        items = list(xs)
        n = len(items)
        if n == 0:
            return []

        if contexts is None:
            contexts_list = [None] * n
        else:
            contexts_list = list(contexts)
            if len(contexts_list) != n:
                contexts_list = (contexts_list + [None] * n)[:n]

        if n < max(1, self.min_batch_size) or int(self.max_workers or 0) == 1:
            return [self.repair(items[i], contexts_list[i]) for i in range(n)]

        backend = self.backend
        if backend not in ("thread", "process"):
            backend = "thread"

        if backend == "process":
            try:
                import pickle

                pickle.dumps(self.inner)
            except Exception:
                backend = "thread"

        try:
            if backend == "process":
                from concurrent.futures import ProcessPoolExecutor

                tasks = [(self.inner, items[i], contexts_list[i]) for i in range(n)]
                with ProcessPoolExecutor(max_workers=self.max_workers) as ex:
                    return list(ex.map(_parallel_repair_task, tasks, chunksize=self.chunk_size))

            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
                futures = [ex.submit(self.repair, items[i], contexts_list[i]) for i in range(n)]
                return [f.result() for f in futures]
        except Exception:
            # Fallback: serial repair
            return [self.repair(items[i], contexts_list[i]) for i in range(n)]


class InitPlugin(Protocol):
    def initialize(self, problem: Any, context: Optional[dict] = None) -> Any:
        ...


class MutationPlugin(Protocol):
    def mutate(self, x: Any, context: Optional[dict] = None) -> Any:
        ...


class CrossoverPlugin(Protocol):
    def crossover(self, parent1: Any, parent2: Any, context: Optional[dict] = None) -> tuple[Any, Any]:
        ...


@dataclass
class RepresentationPipeline:
    encoder: Optional[EncodingPlugin] = None
    repair: Optional[RepairPlugin] = None
    initializer: Optional[InitPlugin] = None
    # Optional: weighted initialization strategy
    initializers: Optional[List[Tuple[InitPlugin, float]]] = field(default=None)
    max_init_attempts: int = 5
    validate_constraints: bool = False
    log_validation_failures: bool = False
    mutator: Optional[MutationPlugin] = None
    crossover: Optional[CrossoverPlugin] = None

    # --- Engineering safeguards (opt-in; defaults preserve existing behavior) ---
    transactional: bool = False
    protect_input: bool = False
    copy_context: bool = False
    threadsafe: bool = False
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False, compare=False)

    def _maybe_lock(self):
        return self._lock if self.threadsafe else contextlib.nullcontext()

    def _prepare_context(self, context: Optional[dict]) -> Optional[dict]:
        if context is None:
            return None
        if not self.copy_context:
            return context
        try:
            return dict(context)
        except Exception:
            return context

    def _prepare_input(self, x: Any) -> Any:
        if not (self.protect_input or self.transactional):
            return x
        if isinstance(x, np.ndarray):
            return x.copy()
        return x

    def init(self, problem: Any, context: Optional[dict] = None) -> Any:
        if self.initializer is None and not self.initializers:
            raise ValueError("initializer is required for init()")

        attempts = max(1, self.max_init_attempts)
        last_exc: Optional[BaseException] = None
        context_in = self._prepare_context(context)

        with self._maybe_lock():
            for _ in range(attempts):
                try:
                    init_plugin = self._choose_initializer()
                    x = init_plugin.initialize(problem, context_in)
                    if self.repair is not None:
                        x = self.repair.repair(x, context_in)

                    if not self.validate_constraints:
                        return x

                    if self._is_feasible(problem, x, context_in):
                        return x
                    if self.log_validation_failures:
                        print("[WARN] Representation init infeasible; retrying")
                except Exception as exc:
                    last_exc = exc
                    if self.log_validation_failures:
                        print("[WARN] Representation init raised; retrying")

        if last_exc is not None and 'x' not in locals():
            raise last_exc

        # If all attempts fail, return last candidate for compatibility
        return x

    def mutate(self, x: Any, context: Optional[dict] = None) -> Any:
        if self.mutator is None:
            raise ValueError("mutator is required for mutate()")

        original = x
        x_in = self._prepare_input(x)
        context_in = self._prepare_context(context)

        with self._maybe_lock():
            try:
                x_out = self.mutator.mutate(x_in, context_in)
                if self.repair is not None:
                    x_out = self.repair.repair(x_out, context_in)
                return x_out
            except Exception:
                if self.transactional:
                    return original
                raise

    def repair_one(self, x: Any, context: Optional[dict] = None) -> Any:
        """Apply repair only (if configured)."""
        if self.repair is None:
            return x
        original = x
        x_in = self._prepare_input(x)
        context_in = self._prepare_context(context)
        with self._maybe_lock():
            try:
                return self.repair.repair(x_in, context_in)
            except Exception:
                if self.transactional:
                    return original
                raise

    # ------------------------------------------------------------------
    # Batch helpers (best-effort; falls back to per-item calls)
    # ------------------------------------------------------------------
    def encode_batch(self, xs: Any, contexts: Optional[Iterable[Optional[dict]]] = None) -> Any:
        if self.encoder is None:
            return xs
        if hasattr(self.encoder, 'encode_batch') and callable(getattr(self.encoder, 'encode_batch')):
            return self.encoder.encode_batch(xs, contexts)
        if contexts is None:
            return [self.encode(x) for x in xs]
        return [self.encode(x, context=c) for x, c in zip(xs, contexts)]

    def decode_batch(self, xs: Any, contexts: Optional[Iterable[Optional[dict]]] = None) -> Any:
        if self.encoder is None:
            return xs
        if hasattr(self.encoder, 'decode_batch') and callable(getattr(self.encoder, 'decode_batch')):
            return self.encoder.decode_batch(xs, contexts)
        if contexts is None:
            return [self.decode(x) for x in xs]
        return [self.decode(x, context=c) for x, c in zip(xs, contexts)]

    def repair_batch(self, xs: Any, contexts: Optional[Iterable[Optional[dict]]] = None) -> Any:
        if self.repair is None:
            return xs
        if hasattr(self.repair, 'repair_batch') and callable(getattr(self.repair, 'repair_batch')):
            return self.repair.repair_batch(xs, contexts)
        if contexts is None:
            return [self.repair_one(x) for x in xs]
        return [self.repair_one(x, context=c) for x, c in zip(xs, contexts)]

    def mutate_batch(self, xs: Any, contexts: Optional[Iterable[Optional[dict]]] = None) -> Any:
        if self.mutator is None:
            raise ValueError("mutator is required for mutate_batch()")
        if hasattr(self.mutator, 'mutate_batch') and callable(getattr(self.mutator, 'mutate_batch')):
            x_out = self.mutator.mutate_batch(xs, contexts)
            return self.repair_batch(x_out, contexts)
        if contexts is None:
            return [self.mutate(x) for x in xs]
        return [self.mutate(x, context=c) for x, c in zip(xs, contexts)]

    def decode(self, x: Any, context: Optional[dict] = None) -> Any:
        if self.encoder is None:
            return x
        return self.encoder.decode(x, context)

    def encode(self, x: Any, context: Optional[dict] = None) -> Any:
        if self.encoder is None:
            return x
        return self.encoder.encode(x, context)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _choose_initializer(self) -> InitPlugin:
        if self.initializer is not None:
            return self.initializer
        assert self.initializers, "initializers must not be empty when initializer is None"
        weights = np.array([w for _, w in self.initializers], dtype=float)
        if weights.sum() <= 0:
            weights = np.ones_like(weights) / len(weights)
        else:
            weights = weights / weights.sum()
        idx = np.random.choice(len(self.initializers), p=weights)
        return self.initializers[idx][0]

    def _is_feasible(self, problem: Any, x: Any, context: Optional[dict]) -> bool:
        try:
            if hasattr(problem, "evaluate_constraints"):
                cons = problem.evaluate_constraints(x)
                cons_arr = np.asarray(cons, dtype=float).flatten()
                return float(np.sum(np.maximum(cons_arr, 0.0))) <= 1e-10
        except Exception:
            if self.log_validation_failures:
                print("[WARN] Representation init constraint check raised; treating as infeasible")
            return False
        return True


def _bounds_to_arrays(bounds: Any, dimension: int) -> Tuple[np.ndarray, np.ndarray]:
    if bounds is None:
        low = np.full(dimension, -np.inf, dtype=float)
        high = np.full(dimension, np.inf, dtype=float)
        return low, high
    arr = np.asarray(bounds, dtype=float)
    if arr.shape[0] != dimension:
        raise ValueError("bounds length must match dimension")
    return arr[:, 0], arr[:, 1]


class ContinuousRepresentation:
    key = "continuous"

    def __init__(self, dimension: int, bounds: Optional[List[Tuple[float, float]]] = None):
        self.dimension = dimension
        self.bounds = bounds or [(-np.inf, np.inf)] * dimension
        self._constraints: List[Any] = []
        self._low, self._high = _bounds_to_arrays(self.bounds, self.dimension)

    def add_constraint(self, constraint: Any) -> None:
        self._constraints.append(constraint)

    def check_constraints(self, x: np.ndarray) -> bool:
        if self._constraints:
            return all(constraint.check(x) for constraint in self._constraints)
        arr = np.asarray(x, dtype=float)
        return bool(np.all(arr >= self._low) and np.all(arr <= self._high))

    def encode(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(x, dtype=float)

    def decode(self, x: np.ndarray) -> np.ndarray:
        arr = np.asarray(x, dtype=float)
        return np.clip(arr, self._low, self._high)

    def repair(self, x: np.ndarray) -> np.ndarray:
        repaired = np.clip(np.asarray(x, dtype=float), self._low, self._high)
        for constraint in self._constraints:
            repaired = constraint.repair(repaired)
        return repaired


class IntegerRepresentation:
    key = "integer"

    def __init__(self, dimension: int, bounds: Optional[List[Tuple[int, int]]] = None):
        self.dimension = dimension
        self.bounds = bounds or [(-np.inf, np.inf)] * dimension
        self._constraints: List[Any] = []
        self._low, self._high = _bounds_to_arrays(self.bounds, self.dimension)

    def add_constraint(self, constraint: Any) -> None:
        self._constraints.append(constraint)

    def check_constraints(self, x: np.ndarray) -> bool:
        if self._constraints:
            return all(constraint.check(x) for constraint in self._constraints)
        arr = np.asarray(x, dtype=float)
        return bool(np.all(arr >= self._low) and np.all(arr <= self._high))

    def encode(self, x: np.ndarray) -> np.ndarray:
        arr = np.asarray(x, dtype=float)
        arr = np.round(arr)
        return np.clip(arr, self._low, self._high)

    def decode(self, x: np.ndarray) -> np.ndarray:
        arr = np.asarray(x, dtype=float)
        arr = np.round(arr)
        arr = np.clip(arr, self._low, self._high)
        return arr.astype(int)

    def repair(self, x: np.ndarray) -> np.ndarray:
        repaired = np.clip(np.round(np.asarray(x, dtype=float)), self._low, self._high)
        for constraint in self._constraints:
            repaired = constraint.repair(repaired)
        return repaired.astype(int)


class PermutationRepresentation:
    key = "permutation"

    def __init__(self, size: int):
        self.size = size
        self.dimension = size

    def encode(self, x: np.ndarray) -> np.ndarray:
        arr = np.asarray(x, dtype=float).ravel()
        if arr.size != self.size:
            raise ValueError("input length must match permutation size")
        return np.argsort(arr).astype(int)

    def decode(self, x: np.ndarray) -> np.ndarray:
        arr = np.asarray(x, dtype=int).ravel()
        if arr.size != self.size:
            raise ValueError("input length must match permutation size")
        return _fix_permutation(arr, self.size)

    def generate_random(self) -> np.ndarray:
        return np.random.permutation(self.size)


class MixedRepresentation:
    def __init__(self, representations: List[Any]):
        self.representations = list(representations)
        self.total_dimension = int(sum(rep.dimension for rep in self.representations))
        self._keys = [self._rep_key(rep, idx) for idx, rep in enumerate(self.representations)]

    def _rep_key(self, rep: Any, idx: int) -> str:
        if hasattr(rep, "key"):
            return str(getattr(rep, "key"))
        name = rep.__class__.__name__.lower().replace("representation", "")
        return name or f"var_{idx}"

    def _select_input(self, solution: Any, idx: int, key: str) -> Any:
        if isinstance(solution, dict):
            if key in solution:
                return solution[key]
            if idx in solution:
                return solution[idx]
            raise KeyError(f"missing input for representation '{key}'")
        if isinstance(solution, (list, tuple)):
            return solution[idx]
        raise TypeError("mixed representation input must be dict or list")

    def encode(self, solution: Any) -> np.ndarray:
        parts = []
        for idx, rep in enumerate(self.representations):
            key = self._keys[idx]
            segment = self._select_input(solution, idx, key)
            parts.append(np.asarray(rep.encode(segment), dtype=float).ravel())
        return np.concatenate(parts) if parts else np.array([])

    def decode(self, encoded: np.ndarray) -> Any:
        arr = np.asarray(encoded, dtype=float).ravel()
        out = {}
        offset = 0
        for idx, rep in enumerate(self.representations):
            dim = int(rep.dimension)
            chunk = arr[offset:offset + dim]
            offset += dim
            out[self._keys[idx]] = rep.decode(chunk)
        return out


def _fix_permutation(arr: np.ndarray, size: int) -> np.ndarray:
    arr = np.asarray(arr, dtype=int).ravel()
    if arr.size != size:
        raise ValueError("input length must match permutation size")
    arr = np.clip(arr, 0, size - 1)
    seen = set()
    missing = [i for i in range(size) if i not in arr]
    for idx, val in enumerate(arr):
        if val in seen:
            arr[idx] = missing.pop(0)
        else:
            seen.add(val)
    return arr.astype(int)
