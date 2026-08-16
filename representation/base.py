"""
Representation pipeline for nsgablack solvers.

Inherits the unified RepresentationBase from blackbase and implements
init/decode/repair/mutate through the blackbase kernel slot mechanism.
"""

import contextlib
import threading
from typing import Iterable, Mapping, Optional, MutableMapping, Sequence, Any

import numpy as np

from blackbase.abc import RepresentationBase
from blackbase.context.context_keys import KEY_METRICS, KEY_PROBLEM
from blackbase.kernel import (
    PipelineSlotSpec,
    PipelineSpec,
    OrchestrationPolicy,
    PipelineOrchestrator,
    PipelineKernelBuild,
    build_pipeline_kernel,
    normalize_slot_name,
    get_method_for_slot,
    is_pipeline_slot,
)


class RepresentationPipeline(RepresentationBase):
    """
    Representation pipeline that dispatches through the blackbase kernel.

    Inherits RepresentationBase and implements init/decode/repair/mutate
    by delegating to kernel slots. Each slot is backed by an operator
    registered at construction time.
    """

    name = "representation_pipeline"
    context_requires = ("candidate.unknown_state",)
    context_provides = ("candidate.model",)
    context_mutates = ("candidate.repaired_state",)
    context_cache = ()
    artifact_requires = ()
    artifact_provides = ()
    phase_in = ()
    phase_out = ()
    context_notes = "Aggregates context contracts from configured pipeline operators."
    doctor_allow_not_implemented = ("encode",)

    def __init__(
        self,
        initializer=None,
        mutator=None,
        repair=None,
        encoder=None,
        decoder=None,
        **kwargs,
    ):
        self._initializer = initializer
        self._mutator = mutator
        self._repair = repair
        self._encoder = encoder
        self._decoder = decoder
        self.initializers = list(kwargs.pop("initializers", ()) or ())
        self.max_init_attempts = max(1, int(kwargs.pop("max_init_attempts", 5)))
        self.validate_constraints = bool(kwargs.pop("validate_constraints", False))
        self.log_validation_failures = bool(kwargs.pop("log_validation_failures", False))
        self.crossover = kwargs.pop("crossover", None)
        self.transactional = bool(kwargs.pop("transactional", False))
        self.protect_input = bool(kwargs.pop("protect_input", False))
        self.copy_context = bool(kwargs.pop("copy_context", False))
        self.threadsafe = bool(kwargs.pop("threadsafe", False))
        self._lock = threading.RLock()
        random_seed = kwargs.pop("random_seed", None)
        self._rng = np.random.default_rng()
        self._random_seed: Optional[int] = None
        self._extra = kwargs

        slots = []
        if initializer is not None:
            slots.append({"slot": "initializer", "operators": ["_init"]})
        if mutator is not None:
            slots.append({"slot": "mutate", "operators": ["_mut"]})
        if repair is not None:
            slots.append({"slot": "repair", "operators": ["_rep"]})
        if encoder is not None:
            slots.append({"slot": "encode", "operators": ["_enc"]})
        if decoder is not None:
            slots.append({"slot": "decode", "operators": ["_dec"]})

        spec = {"key": "representation", "slots": slots} if slots else None
        registry = {
            "_init": initializer,
            "_mut": mutator,
            "_rep": repair,
            "_enc": encoder,
            "_dec": decoder,
        }
        registry = {k: v for k, v in registry.items() if v is not None}

        self._kernel = build_pipeline_kernel(spec, operator_registry=registry) if registry else None
        self.set_random_seed(random_seed)

    @property
    def initializer(self):
        return self._initializer

    @property
    def mutator(self):
        return self._mutator

    @property
    def encoder(self):
        return self._encoder

    @property
    def decoder(self):
        return self._decoder

    def set_random_seed(self, seed: Optional[int]) -> None:
        """Seed the pipeline and every RNG-owning representation operator."""

        self._random_seed = None if seed is None else int(seed)
        root = np.random.SeedSequence(self._random_seed)
        self._rng = np.random.default_rng(root)
        components = [
            self._initializer,
            self._mutator,
            self._repair,
            self._encoder,
            self._decoder,
            self.crossover,
            *(item[0] for item in self.initializers),
        ]
        unique = []
        seen: set[int] = set()
        for component in components:
            if component is None or id(component) in seen:
                continue
            seen.add(id(component))
            unique.append(component)
        for component, child_sequence in zip(unique, root.spawn(len(unique))):
            child_seed = int(child_sequence.generate_state(1, dtype=np.uint64)[0])
            setter = getattr(component, "set_random_seed", None)
            if callable(setter):
                setter(child_seed)
            elif hasattr(component, "_rng"):
                setattr(component, "_rng", np.random.default_rng(child_seed))

    def get_context_contract(self) -> dict[str, Any]:
        """Aggregate the pipeline contract with every configured operator."""

        from blackbase.context import get_component_contract

        requires = set(self.context_requires or ())
        provides = set(self.context_provides or ())
        mutates = set(self.context_mutates or ())
        cache = set(self.context_cache or ())
        artifact_requires = set(self.artifact_requires or ())
        artifact_provides = set(self.artifact_provides or ())
        phase_in = set(self.phase_in or ())
        phase_out = set(self.phase_out or ())
        notes = [str(self.context_notes)] if self.context_notes else []

        for component_name, component in (
            ("initializer", self._initializer),
            ("mutator", self._mutator),
            ("repair", self._repair),
            ("encoder", self._encoder),
            ("decoder", self._decoder),
        ):
            contract = get_component_contract(component)
            if contract is None:
                continue
            requires.update(contract.requires)
            provides.update(contract.provides)
            mutates.update(contract.mutates)
            cache.update(contract.cache)
            artifact_requires.update(contract.artifact_requires)
            artifact_provides.update(contract.artifact_provides)
            phase_in.update(contract.phase_in)
            phase_out.update(contract.phase_out)
            if contract.notes:
                notes.append(f"{component_name}: {contract.notes}")

        return {
            "requires": tuple(sorted(requires)),
            "provides": tuple(sorted(provides)),
            "mutates": tuple(sorted(mutates)),
            "cache": tuple(sorted(cache)),
            "artifact_requires": tuple(sorted(artifact_requires)),
            "artifact_provides": tuple(sorted(artifact_provides)),
            "phase_in": tuple(sorted(phase_in)),
            "phase_out": tuple(sorted(phase_out)),
            "notes": " | ".join(notes) or None,
        }

    # --- RepresentationBase implementation ---

    def set_repair(self, repair_operator):
        """Replace the repair operator at runtime (rebuilds kernel slot)."""
        self._repair = repair_operator
        self._rebuild_kernel()

    def set_mutator(self, mutator_operator):
        """Replace the mutator operator at runtime (rebuilds kernel slot)."""
        self._mutator = mutator_operator
        self._rebuild_kernel()

    def _rebuild_kernel(self):
        """Rebuild the pipeline kernel after operator changes."""
        slots = []
        if self._initializer is not None:
            slots.append({"slot": "initializer", "operators": ["_init"]})
        if self._mutator is not None:
            slots.append({"slot": "mutate", "operators": ["_mut"]})
        if self._repair is not None:
            slots.append({"slot": "repair", "operators": ["_rep"]})
        if self._encoder is not None:
            slots.append({"slot": "encode", "operators": ["_enc"]})
        if self._decoder is not None:
            slots.append({"slot": "decode", "operators": ["_dec"]})

        spec = {"key": "representation", "slots": slots} if slots else None
        registry = {
            "_init": self._initializer,
            "_mut": self._mutator,
            "_rep": self._repair,
            "_enc": self._encoder,
            "_dec": self._decoder,
        }
        registry = {k: v for k, v in registry.items() if v is not None}
        self._kernel = build_pipeline_kernel(spec, operator_registry=registry) if registry else None

    def _maybe_lock(self):
        return self._lock if self.threadsafe else contextlib.nullcontext()

    def _prepare_context(self, context: Optional[Mapping[str, Any]]) -> MutableMapping[str, Any]:
        if context is None:
            return {}
        if self.copy_context or not isinstance(context, MutableMapping):
            return dict(context)
        return context

    def _prepare_input(self, value: Any) -> Any:
        if not (self.protect_input or self.transactional):
            return value
        if isinstance(value, np.ndarray):
            return value.copy()
        return value

    def _choose_initializer(self):
        if self._initializer is not None:
            return self._initializer
        if not self.initializers:
            raise ValueError("initializer is required for init()")
        weights = np.asarray([float(weight) for _, weight in self.initializers], dtype=float)
        weights = np.ones_like(weights) if float(np.sum(weights)) <= 0.0 else weights
        weights = weights / float(np.sum(weights))
        return self.initializers[int(self._rng.choice(len(self.initializers), p=weights))][0]

    def init(self, problem_or_context=None, context=None):
        """Create a candidate, accepting both blackbase and legacy nsgablack call forms."""
        if context is None and isinstance(problem_or_context, Mapping):
            context_in = self._prepare_context(problem_or_context)
            problem = context_in.get(KEY_PROBLEM, context_in)
        else:
            context_in = self._prepare_context(context)
            problem = problem_or_context
            context_in.setdefault(KEY_PROBLEM, problem)

        last_error: Optional[BaseException] = None
        last_candidate: Any = None
        with self._maybe_lock():
            for _ in range(self.max_init_attempts):
                try:
                    initializer = self._choose_initializer()
                    if initializer is self._initializer and self._kernel is not None:
                        candidate = self._kernel.run_slot("initializer", problem, context_in)
                    else:
                        candidate = initializer.initialize(problem, context_in)
                    candidate = self.repair(candidate, context_in)
                    last_candidate = candidate
                    if not self.validate_constraints or self._is_feasible(problem, candidate):
                        return candidate
                    if self.log_validation_failures:
                        print("[WARN] Representation init infeasible; retrying")
                except Exception as exc:
                    last_error = exc
                    if self.log_validation_failures:
                        print("[WARN] Representation init raised; retrying")
        if last_candidate is not None:
            return last_candidate
        if last_error is not None:
            raise last_error
        raise ValueError("initializer is required for init()")

    def decode(self, state, context=None):
        """Decode candidate via kernel decoder slot."""
        context_in = self._prepare_context(context)
        if self._decoder is not None and self._kernel:
            return self._kernel.run_slot("decode", state, context_in)
        return state

    def encode(self, model, context=None):
        """Encode model via kernel encoder slot."""
        context_in = self._prepare_context(context)
        if self._encoder is not None and self._kernel:
            return self._kernel.run_slot("encode", model, context_in)
        return model

    def repair(self, state, context=None):
        """Repair candidate via kernel repair slot."""
        if self._repair is None:
            return state
        original = state
        state_in = self._prepare_input(state)
        context_in = self._prepare_context(context)
        with self._maybe_lock():
            try:
                return self._kernel.run_slot("repair", state_in, context_in)
            except Exception:
                if self.transactional:
                    return original
                raise

    def mutate(self, state, context=None):
        """Mutate then repair a candidate, preserving transactional semantics."""
        if self._mutator is None:
            raise ValueError("mutator is required for mutate()")
        original = state
        state_in = self._prepare_input(state)
        context_in = self._prepare_context(context)
        with self._maybe_lock():
            try:
                mutated = self._kernel.run_slot("mutate", state_in, context_in)
                if self._repair is not None:
                    mutated = self._kernel.run_slot("repair", mutated, context_in)
                return mutated
            except Exception:
                if self.transactional:
                    return original
                raise

    def encode_batch(self, states, contexts: Optional[Iterable[Optional[dict]]] = None, *, context=None):
        if self._encoder is None:
            return states
        context_items = self._normalize_batch_contexts(states, contexts, context)
        batch = getattr(self._encoder, "encode_batch", None)
        if callable(batch) and contexts is not None:
            return batch(states, context_items)
        return [self.encode(state, context_items[idx]) for idx, state in enumerate(states)]

    def decode_batch(self, states, contexts: Optional[Iterable[Optional[dict]]] = None, *, context=None):
        if self._decoder is None:
            return states
        context_items = self._normalize_batch_contexts(states, contexts, context)
        batch = getattr(self._decoder, "decode_batch", None)
        if callable(batch) and contexts is not None:
            return batch(states, context_items)
        return [self.decode(state, context_items[idx]) for idx, state in enumerate(states)]

    def repair_batch(self, states, contexts: Optional[Iterable[Optional[dict]]] = None, *, context=None):
        if self._repair is None:
            return states
        context_items = self._normalize_batch_contexts(states, contexts, context)
        batch = getattr(self._repair, "repair_batch", None)
        if callable(batch):
            try:
                return batch(states, contexts=context_items)
            except TypeError:
                return batch(states, context_items)
        return [self.repair(state, context_items[idx]) for idx, state in enumerate(states)]

    def mutate_batch(self, states, contexts: Optional[Iterable[Optional[dict]]] = None, *, context=None):
        if self._mutator is None:
            raise ValueError("mutator is required for mutate_batch()")
        context_items = self._normalize_batch_contexts(states, contexts, context)
        batch = getattr(self._mutator, "mutate_batch", None)
        if callable(batch):
            try:
                mutated = batch(states, contexts=context_items)
            except TypeError:
                mutated = batch(states, context_items)
            return self.repair_batch(mutated, contexts=context_items)
        return [self.mutate(state, context_items[idx]) for idx, state in enumerate(states)]

    @staticmethod
    def _normalize_batch_contexts(states, contexts, context):
        count = len(states)
        if contexts is None:
            return [context] * count
        context_items = list(contexts)
        if len(context_items) != count:
            raise ValueError("contexts length must match states length")
        return context_items

    def _is_feasible(self, problem: Any, candidate: Any) -> bool:
        evaluator = getattr(problem, "evaluate_constraints", None)
        if not callable(evaluator):
            return True
        try:
            values = np.asarray(evaluator(candidate), dtype=float).reshape(-1)
            return float(np.sum(np.maximum(values, 0.0))) <= 1e-10
        except Exception:
            return False

    # --- Legacy API compatibility ---

    def initialize(self, problem, context: Optional[MutableMapping] = None):
        """Legacy initializer spelling used by SolverBase."""
        return self.init(problem, context=context)

    def transform(self, value, context: Optional[MutableMapping] = None):
        """Legacy transform method."""
        result = value
        if self._initializer:
            result = self.initialize(result, context)
        if self._encoder:
            result = self.encode(result, context)
        return result

    def describe(self) -> dict:
        """Describe the representation pipeline configuration."""
        return {
            "name": self.name,
            "class": self.__class__.__name__,
            "initializer": type(self._initializer).__name__ if self._initializer else None,
            "mutator": type(self._mutator).__name__ if self._mutator else None,
            "repair": type(self._repair).__name__ if self._repair else None,
            "encoder": type(self._encoder).__name__ if self._encoder else None,
            "decoder": type(self._decoder).__name__ if self._decoder else None,
        }


class ParallelRepair:
    """Run batch repair concurrently with auditable per-item fallback."""

    context_requires = ("candidate.unknown_state",)
    context_provides = ("candidate.repaired_state",)
    context_mutates = ()
    context_cache = ()

    def __init__(
        self,
        inner,
        *,
        backend: str = "thread",
        max_workers: Optional[int] = None,
        min_batch_size: int = 16,
        chunk_size: Optional[int] = None,
        verbose: bool = False,
        strict: bool = False,
        report_errors_to_context: bool = False,
        error_report_key: str = "parallel_repair_errors",
    ) -> None:
        self.inner = inner
        self.backend = str(backend or "thread")
        self.max_workers = max_workers
        self.min_batch_size = int(min_batch_size)
        self.chunk_size = chunk_size
        self.verbose = bool(verbose)
        self.strict = bool(strict)
        self.last_batch_errors: list[dict[str, Any]] = []
        self.report_errors_to_context = bool(report_errors_to_context)
        self.error_report_key = str(error_report_key or "parallel_repair_errors")

    def _report_error(self, context: Optional[dict], record: dict[str, Any]) -> None:
        if not self.report_errors_to_context or not isinstance(context, dict):
            return
        metrics = context.get(KEY_METRICS)
        if not isinstance(metrics, dict):
            metrics = {}
            context[KEY_METRICS] = metrics
        bucket = metrics.get(self.error_report_key)
        if not isinstance(bucket, list):
            bucket = []
            metrics[self.error_report_key] = bucket
        bucket.append(dict(record))

    def repair(self, candidate: Any, context: Optional[dict] = None) -> Any:
        repair = getattr(self.inner, "repair", None)
        if callable(repair):
            return repair(candidate, context)
        if callable(self.inner):
            return self.inner(candidate, context)
        raise TypeError("ParallelRepair inner component must define repair() or be callable")

    def __call__(self, candidates: Sequence[Any], context: Optional[MutableMapping] = None):
        return self.repair_batch(candidates, contexts=None if context is None else [context] * len(candidates))

    def repair_batch(
        self,
        candidates: Sequence[Any],
        contexts: Optional[Iterable[Optional[dict]]] = None,
        *,
        context: Optional[dict] = None,
    ) -> list[Any]:
        items = [] if candidates is None else list(candidates)
        if not items:
            return []
        if contexts is None:
            context_items = [context] * len(items)
        else:
            context_items = list(contexts)
            if len(context_items) != len(items):
                raise ValueError("contexts length must match candidates length")

        self.last_batch_errors = []
        if len(items) < max(1, self.min_batch_size) or int(self.max_workers or 0) == 1:
            return [self.repair(item, context_items[idx]) for idx, item in enumerate(items)]

        backend = self.backend if self.backend in {"thread", "process"} else "thread"
        if backend == "process":
            try:
                import pickle

                pickle.dumps(self.inner)
            except Exception:
                backend = "thread"

        if backend == "process":
            from concurrent.futures import ProcessPoolExecutor

            tasks = [(self.inner, items[idx], context_items[idx]) for idx in range(len(items))]
            try:
                with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                    return list(executor.map(_parallel_repair_task, tasks, chunksize=self.chunk_size or 1))
            except Exception as exc:
                if self.strict:
                    raise
                record = {"index": -1, "phase": "batch_fallback", "error": f"{type(exc).__name__}: {exc}"}
                self.last_batch_errors.append(record)
                for item_context in context_items:
                    self._report_error(item_context, record)
                return [self.repair(item, context_items[idx]) for idx, item in enumerate(items)]

        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self.repair, item, context_items[idx])
                for idx, item in enumerate(items)
            ]
            output: list[Any] = [None] * len(items)
            failed: list[int] = []
            for idx, future in enumerate(futures):
                try:
                    output[idx] = future.result()
                except Exception as exc:
                    failed.append(idx)
                    record = {
                        "index": idx,
                        "phase": "parallel",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                    self.last_batch_errors.append(record)
                    self._report_error(context_items[idx], record)

        if failed and self.strict:
            raise RuntimeError(f"ParallelRepair strict failure: {self.last_batch_errors[0]['error']}")
        for idx in failed:
            try:
                output[idx] = self.repair(items[idx], context_items[idx])
            except Exception as exc:
                record = {
                    "index": idx,
                    "phase": "serial_fallback",
                    "error": f"{type(exc).__name__}: {exc}",
                }
                self.last_batch_errors.append(record)
                self._report_error(context_items[idx], record)
                raise
        return output


def _parallel_repair_task(task: tuple[Any, Any, Optional[dict]]) -> Any:
    inner, candidate, context = task
    repair = getattr(inner, "repair", None)
    return repair(candidate, context) if callable(repair) else inner(candidate, context)


class ContinuousRepresentation:
    """Legacy continuous representation."""

    key = "continuous"
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()

    def __init__(self, dimension: int, bounds: Optional[Sequence] = None):
        self.dimension = int(dimension)
        self.bounds = list(bounds) if bounds is not None else [(-np.inf, np.inf)] * self.dimension
        self._constraints: list[Any] = []
        self._low, self._high = _bounds_to_arrays(self.bounds, self.dimension)

    def initialize(self, context: Optional[MutableMapping] = None):
        _ = context
        return np.random.uniform(
            low=self._low,
            high=self._high,
            size=self.dimension,
        )

    def add_constraint(self, constraint: Any) -> None:
        self._constraints.append(constraint)

    def check_constraints(self, candidate: np.ndarray) -> bool:
        if self._constraints:
            return all(constraint.check(candidate) for constraint in self._constraints)
        value = np.asarray(candidate, dtype=float)
        return bool(np.all(value >= self._low) and np.all(value <= self._high))

    def encode(self, candidate: np.ndarray) -> np.ndarray:
        return np.asarray(candidate, dtype=float)

    def decode(self, state: np.ndarray) -> np.ndarray:
        return np.clip(np.asarray(state, dtype=float), self._low, self._high)

    def repair(self, candidate: np.ndarray) -> np.ndarray:
        repaired = self.decode(candidate)
        for constraint in self._constraints:
            repaired = constraint.repair(repaired)
        return np.asarray(repaired, dtype=float)


class IntegerRepresentation:
    """Legacy integer representation."""

    key = "integer"
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()

    def __init__(self, dimension: int, bounds: Optional[Sequence] = None):
        self.dimension = int(dimension)
        self.bounds = list(bounds) if bounds is not None else [(-np.inf, np.inf)] * self.dimension
        self._constraints: list[Any] = []
        self._low, self._high = _bounds_to_arrays(self.bounds, self.dimension)

    def initialize(self, context: Optional[MutableMapping] = None):
        _ = context
        return np.random.randint(
            low=np.asarray(self._low, dtype=int),
            high=np.asarray(self._high, dtype=int) + 1,
            size=self.dimension,
        )

    def add_constraint(self, constraint: Any) -> None:
        self._constraints.append(constraint)

    def check_constraints(self, candidate: np.ndarray) -> bool:
        if self._constraints:
            return all(constraint.check(candidate) for constraint in self._constraints)
        value = np.asarray(candidate, dtype=float)
        return bool(np.all(value >= self._low) and np.all(value <= self._high))

    def encode(self, candidate: np.ndarray) -> np.ndarray:
        return np.clip(np.round(np.asarray(candidate, dtype=float)), self._low, self._high)

    def decode(self, state: np.ndarray) -> np.ndarray:
        return self.encode(state).astype(int)

    def repair(self, candidate: np.ndarray) -> np.ndarray:
        repaired = self.encode(candidate)
        for constraint in self._constraints:
            repaired = constraint.repair(repaired)
        return np.asarray(repaired, dtype=int)


class PermutationRepresentation:
    """Legacy permutation representation."""

    key = "permutation"
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()

    def __init__(self, size: int):
        self.size = int(size)
        self.dimension = self.size
        self._rng = np.random.default_rng()

    def initialize(self, context: Optional[MutableMapping] = None):
        _ = context
        return self.generate_random()

    def encode(self, candidate: np.ndarray) -> np.ndarray:
        value = np.asarray(candidate, dtype=float).reshape(-1)
        if value.size != self.size:
            raise ValueError("input length must match permutation size")
        return np.argsort(value).astype(int)

    def decode(self, state: np.ndarray) -> np.ndarray:
        return _fix_permutation(state, self.size)

    def generate_random(self) -> np.ndarray:
        return self._rng.permutation(self.size)


class MixedRepresentation:
    """Legacy mixed representation."""

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()

    def __init__(self, representations: Sequence):
        self.representations = list(representations)
        self.total_dimension = int(sum(int(rep.dimension) for rep in self.representations))
        self.dimension = self.total_dimension
        self._keys = [self._representation_key(rep, idx) for idx, rep in enumerate(self.representations)]

    def initialize(self, context: Optional[MutableMapping] = None):
        result = [rep.initialize(context) for rep in self.representations]
        return np.concatenate([np.atleast_1d(value) for value in result])

    @staticmethod
    def _representation_key(representation: Any, index: int) -> str:
        key = getattr(representation, "key", None)
        if key:
            return str(key)
        name = type(representation).__name__.lower().replace("representation", "")
        return name or f"var_{index}"

    @staticmethod
    def _select_input(solution: Any, index: int, key: str) -> Any:
        if isinstance(solution, Mapping):
            if key in solution:
                return solution[key]
            if index in solution:
                return solution[index]
            raise KeyError(f"missing input for representation '{key}'")
        if isinstance(solution, (list, tuple)):
            return solution[index]
        raise TypeError("mixed representation input must be a mapping or sequence")

    def encode(self, solution: Any) -> np.ndarray:
        parts = []
        for index, representation in enumerate(self.representations):
            value = self._select_input(solution, index, self._keys[index])
            parts.append(np.asarray(representation.encode(value), dtype=float).reshape(-1))
        return np.concatenate(parts) if parts else np.asarray([], dtype=float)

    def decode(self, state: np.ndarray) -> dict[str, Any]:
        value = np.asarray(state, dtype=float).reshape(-1)
        output: dict[str, Any] = {}
        offset = 0
        for index, representation in enumerate(self.representations):
            width = int(representation.dimension)
            output[self._keys[index]] = representation.decode(value[offset : offset + width])
            offset += width
        return output


def _bounds_to_arrays(bounds: Sequence, dimension: int) -> tuple[np.ndarray, np.ndarray]:
    value = np.asarray(bounds, dtype=float)
    if value.shape != (int(dimension), 2):
        raise ValueError("bounds must have shape (dimension, 2)")
    return value[:, 0], value[:, 1]


def _fix_permutation(state: np.ndarray, size: int) -> np.ndarray:
    value = np.asarray(state, dtype=int).reshape(-1).copy()
    if value.size != int(size):
        raise ValueError("input length must match permutation size")
    value = np.clip(value, 0, int(size) - 1)
    seen: set[int] = set()
    missing = [index for index in range(int(size)) if index not in value]
    for index, item in enumerate(value):
        key = int(item)
        if key in seen:
            value[index] = missing.pop(0)
        else:
            seen.add(key)
    return value.astype(int)


class RepresentationComponentContract:
    """Legacy representation component contract."""

    context_requires = ()
    context_optional = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    requires_metrics = ()
    metrics_fallback = "strict"
    context_notes = ""


__all__ = [
    "RepresentationPipeline",
    "ParallelRepair",
    "ContinuousRepresentation",
    "IntegerRepresentation",
    "PermutationRepresentation",
    "MixedRepresentation",
    "RepresentationComponentContract",
    "PipelineSlotSpec",
    "PipelineSpec",
    "OrchestrationPolicy",
    "PipelineOrchestrator",
    "PipelineKernelBuild",
    "build_pipeline_kernel",
    "normalize_slot_name",
    "get_method_for_slot",
    "is_pipeline_slot",
]
