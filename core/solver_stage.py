"""
Stage orchestration for the Solver/Trainer control plane.

Serial stage execution with artifact flow between stages.
Orthogonal to Adapter-level orchestration (serial_strategy, multi_strategy).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional

from ..utils.context.context_events import record_context_event
from ..utils.context.context_keys import (
    KEY_GENERATION,
    KEY_SNAPSHOT_KEY,
    KEY_SNAPSHOT_SCHEMA,
    KEY_STAGE_ARTIFACTS,
    KEY_STAGE_ARTIFACT_PREFIX,
    KEY_STAGE_INDEX,
    KEY_STAGE_INPUT_ARTIFACTS,
    KEY_STAGE_NAME,
    KEY_STAGE_OUTPUT_ARTIFACTS,
    KEY_STAGE_STATUS,
    KEY_STAGE_TOTAL,
    KEY_STEP,
)
from ..utils.engineering.error_policy import report_soft_error

import logging

logger = logging.getLogger(__name__)

# Inline payloads above this size are pushed to snapshot store.
_MAX_INLINE_BYTES = 1024


# ── helpers ────────────────────────────────────────────────────────────
def _ref_to_dict(ref: ArtifactRef) -> Dict[str, Any]:
    d: Dict[str, Any] = {"key": str(ref.key), "uri": str(ref.uri), "kind": str(ref.kind)}
    if ref.backend:
        d["backend"] = str(ref.backend)
    if ref.schema:
        d["schema"] = str(ref.schema)
    if ref.meta:
        d["meta"] = dict(ref.meta)
    if ref.inline_value is not None:
        d["has_inline"] = True
    return d


def _is_small_payload(obj: Any) -> bool:
    try:
        return len(repr(obj).encode("utf-8")) <= _MAX_INLINE_BYTES
    except Exception:
        return False


# ────────────────────────────────────────────────────────────────────────
# Data classes
# ────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ArtifactRef:
    """Typed reference to an artifact produced by one stage, consumed by another.

    Large artifacts live in SnapshotStore (the ``_ref`` pattern).
    Small payloads may be inlined.
    """

    key: str
    uri: str
    kind: str = "snapshot"  # "snapshot" | "data_ref" | "inline"
    backend: str = "snapshot_store"
    schema: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)
    inline_value: Optional[Any] = None

    def resolve(self, snapshot_store: Optional[Any] = None) -> Any:
        if self.inline_value is not None:
            return self.inline_value
        if snapshot_store is None or not callable(getattr(snapshot_store, "read", None)):
            raise RuntimeError(
                f"Cannot resolve artifact '{self.key}': no snapshot_store available"
            )
        record = snapshot_store.read(self.uri)
        if record is None:
            raise KeyError(
                f"Artifact '{self.key}' not found at uri '{self.uri}'"
            )
        payload = record.data if hasattr(record, "data") else record
        return payload


@dataclass(frozen=True)
class CompletionPolicy:
    """Declares when a stage is considered complete."""

    max_steps: Optional[int] = None
    max_seconds: Optional[float] = None
    convergence_or_stagnation: bool = False
    custom_check: Optional[Callable[[Dict[str, Any]], bool]] = None
    # Check signature: fn({"stage_name": str, "solver": Any, "elapsed": float, ...}) -> bool

    def is_complete(self, *, step: int, elapsed: float, solver: Any, ctx: Dict[str, Any]) -> bool:
        if self.max_steps is not None and step >= self.max_steps:
            return True
        if self.max_seconds is not None and elapsed >= self.max_seconds:
            return True
        if callable(self.custom_check):
            try:
                if self.custom_check({"step": step, "elapsed": elapsed, "solver": solver, **ctx}):
                    return True
            except Exception:
                pass
        return False


@dataclass(frozen=True)
class StageSpec:
    """One stage in an orchestrated pipeline."""

    name: str
    factory: Callable[[], Any]
    completion: CompletionPolicy = field(default_factory=CompletionPolicy)
    input_artifacts: Dict[str, str] = field(default_factory=dict)
    # ^ solver_key → registry_key
    output_artifacts: List[str] = field(default_factory=list)
    # ^ registry keys produced by this stage
    enabled: bool = True
    resource_labels: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ────────────────────────────────────────────────────────────────────────
# StageRunner
# ────────────────────────────────────────────────────────────────────────


class StageRunner:
    """Execute a sequence of StageSpecs with artifact flow between stages.

    This is the core orchestration engine. It is NOT a SolverBase — it is
    a standalone executor that SerialStageSolver wraps for compatibility.
    """

    def __init__(
        self,
        stages: List[StageSpec],
        *,
        artifact_registry: Optional[Dict[str, ArtifactRef]] = None,
        context_store: Optional[Any] = None,
        snapshot_store: Optional[Any] = None,
        global_metadata: Optional[Dict[str, Any]] = None,
        strict: bool = False,
    ) -> None:
        self._stages: List[StageSpec] = [s for s in stages if s.enabled]
        if not self._stages:
            raise ValueError("StageRunner requires at least one enabled stage")
        self._artifact_registry: Dict[str, ArtifactRef] = dict(artifact_registry or {})
        self._context_store = context_store
        self._snapshot_store = snapshot_store
        self._global_metadata = dict(global_metadata or {})
        self._strict = bool(strict)
        self._results: List[Dict[str, Any]] = []

    # -- public read-only accessors --------------------------------------

    @property
    def results(self) -> List[Dict[str, Any]]:
        return list(self._results)

    @property
    def artifact_registry(self) -> Dict[str, ArtifactRef]:
        return dict(self._artifact_registry)

    def get_artifact(self, key: str) -> Optional[ArtifactRef]:
        return self._artifact_registry.get(key)

    def set_artifact(self, key: str, ref: ArtifactRef) -> None:
        self._artifact_registry[str(key)] = ref

    # -- main entry ------------------------------------------------------

    def run(self) -> Dict[str, Any]:
        stage_total = len(self._stages)
        for idx, stage in enumerate(self._stages):
            result = self._run_single_stage(stage, idx, stage_total)
            self._results.append(result)
        return self._merge_results()

    # -- per-stage execution ---------------------------------------------

    def _run_single_stage(
        self, stage: StageSpec, stage_index: int, stage_total: int
    ) -> Dict[str, Any]:
        solver = stage.factory()

        # 1. Inject stage metadata into solver context
        self._inject_stage_meta(solver, stage, stage_index, stage_total)

        # 2. Inject input artifacts
        self._inject_artifacts(solver, stage)

        # 3. Record stage_start event
        self._record_stage_event(solver, stage, stage_index, "stage_start")

        # 4. Run
        start_time = time.time()
        result = self._run_solver(solver, stage)
        elapsed = time.time() - start_time

        # 5. Extract declared output artifacts
        self._extract_artifacts(solver, stage, stage_index)

        # 6. Record stage_complete event
        self._record_stage_event(solver, stage, stage_index, "stage_complete")

        # 7. Teardown solver safely
        self._safe_teardown(solver)

        return {
            "stage_name": stage.name,
            "stage_index": stage_index,
            "elapsed_sec": elapsed,
            "solver_result": result,
            "produced_artifacts": [
                key for key in stage.output_artifacts if key in self._artifact_registry
            ],
        }

    # -- solver lifecycle ------------------------------------------------

    def _run_solver(self, solver: Any, stage: StageSpec) -> Dict[str, Any]:
        """Detect and run the solver/trainer. Supports run(), fit(), or step loop."""

        has_run = callable(getattr(solver, "run", None))
        has_fit = callable(getattr(solver, "fit", None))
        has_step = callable(getattr(solver, "step", None))

        # Override max_steps if solver supports it
        if stage.completion.max_steps is not None:
            if callable(getattr(solver, "set_max_steps", None)):
                solver.set_max_steps(stage.completion.max_steps)

        # fit() path (mlblack Trainer compat)
        if has_fit and not has_run:
            raw = solver.fit()
            return dict(raw) if isinstance(raw, (dict, Mapping)) else {"raw": raw}

        # run() path (nsgablack Solver)
        if has_run:
            raw = solver.run()
            return dict(raw) if isinstance(raw, (dict, Mapping)) else {"raw": raw}

        # step-loop path: manually iterate
        if has_step:
            start_time = time.time()
            step = 0
            while True:
                if solver.stop_requested if hasattr(solver, "stop_requested") else False:
                    break
                ctx: Dict[str, Any] = {}
                if stage.completion.is_complete(
                    step=step, elapsed=time.time() - start_time, solver=solver, ctx=ctx
                ):
                    break
                solver.step()
                step += 1
            return {"steps": step}

        raise RuntimeError(
            f"Stage '{stage.name}' solver has no run(), fit(), or step()"
        )

    def _safe_teardown(self, solver: Any) -> None:
        teardown = getattr(solver, "teardown", None)
        if callable(teardown):
            try:
                teardown()
            except Exception as exc:
                report_soft_error(
                    component="StageRunner",
                    event="solver_teardown",
                    exc=exc,
                    logger=logger,
                    context_store=self._context_store,
                    strict=False,
                    level="warning",
                )

    # -- artifact injection ----------------------------------------------

    def _inject_artifacts(self, solver: Any, stage: StageSpec) -> None:
        if not stage.input_artifacts:
            return

        for solver_key, registry_key in stage.input_artifacts.items():
            ref = self._artifact_registry.get(registry_key)
            if ref is None:
                if self._strict:
                    raise KeyError(
                        f"Required artifact '{registry_key}' not found in registry "
                        f"for stage '{stage.name}' (→ solver key '{solver_key}')"
                    )
                continue

            # Route 1: setter method  e.g. solver.set_pretrained_weights(...)
            setter = getattr(solver, f"set_{solver_key}", None)
            if callable(setter):
                try:
                    payload = ref.resolve(self._snapshot_store)
                    setter(payload)
                    continue
                except Exception:
                    if self._strict:
                        raise

            # Route 2: direct attribute
            if hasattr(solver, solver_key) or not self._strict:
                setattr(solver, solver_key, ref)
                continue

            # Route 3: context store fallback
            store = getattr(solver, "context_store", self._context_store)
            if store is not None and callable(getattr(store, "set", None)):
                store.set(KEY_STAGE_ARTIFACT_PREFIX + solver_key, _ref_to_dict(ref))

        # Also expose the full registry as stage_artifacts in context
        store = getattr(solver, "context_store", self._context_store)
        if store is not None and callable(getattr(store, "set", None)):
            store.set(KEY_STAGE_ARTIFACTS, {
                k: _ref_to_dict(v) for k, v in self._artifact_registry.items()
            })
            store.set(KEY_STAGE_INPUT_ARTIFACTS, dict(stage.input_artifacts))
            store.set(KEY_STAGE_OUTPUT_ARTIFACTS, list(stage.output_artifacts))

    # -- artifact extraction ---------------------------------------------

    def _extract_artifacts(
        self, solver: Any, stage: StageSpec, stage_index: int
    ) -> None:
        if not stage.output_artifacts:
            return

        for artifact_key in stage.output_artifacts:
            ref: Optional[ArtifactRef] = None

            # Route 1: getter method  e.g. solver.get_model_weights_artifact()
            getter = getattr(solver, f"get_{artifact_key}_artifact", None)
            if callable(getter):
                try:
                    raw = getter()
                    if isinstance(raw, ArtifactRef):
                        ref = raw
                except Exception:
                    if self._strict:
                        raise

            # Route 2: snapshot refs in context
            if ref is None:
                ctx = self._read_solver_context(solver)
                snap_key = ctx.get(KEY_SNAPSHOT_KEY)
                if snap_key:
                    ref = ArtifactRef(
                        key=artifact_key,
                        uri=str(snap_key),
                        kind="snapshot",
                        schema=str(ctx.get(KEY_SNAPSHOT_SCHEMA, "")),
                        meta={
                            "generation": ctx.get(KEY_GENERATION),
                            "stage_index": stage_index,
                        },
                    )

            # Route 3: solver attribute
            if ref is None:
                attr = getattr(solver, artifact_key, None)
                if attr is not None:
                    if isinstance(attr, ArtifactRef):
                        ref = attr
                    elif _is_small_payload(attr):
                        ref = ArtifactRef(
                            key=artifact_key,
                            uri="inline",
                            kind="inline",
                            inline_value=attr,
                        )
                    elif self._snapshot_store is not None and callable(
                        getattr(self._snapshot_store, "write", None)
                    ):
                        snap_key = f"stage_{stage_index}.{artifact_key}"
                        try:
                            handle = self._snapshot_store.write(
                                {"data": attr},
                                key=snap_key,
                                schema="artifact_v1",
                            )
                            ref = ArtifactRef(
                                key=artifact_key,
                                uri=str(handle.key),
                                kind="snapshot",
                                meta={"stage_index": stage_index},
                            )
                        except Exception:
                            ref = ArtifactRef(
                                key=artifact_key,
                                uri=snap_key,
                                kind="inline",
                                inline_value=attr,
                            )

            if ref is not None:
                self._artifact_registry[artifact_key] = ref

    @staticmethod
    def _read_solver_context(solver: Any) -> Dict[str, Any]:
        getter = getattr(solver, "get_context", None)
        if callable(getter):
            try:
                return dict(getter() or {})
            except Exception:
                pass
        store = getattr(solver, "context_store", None)
        if store is not None and callable(getattr(store, "to_dict", None)):
            try:
                return dict(store.to_dict() or {})
            except Exception:
                pass
        return {}

    # -- stage metadata injection ----------------------------------------

    def _inject_stage_meta(
        self, solver: Any, stage: StageSpec, stage_index: int, stage_total: int
    ) -> None:
        store = getattr(solver, "context_store", None)
        if store is not None and callable(getattr(store, "set", None)):
            store.set(KEY_STAGE_INDEX, stage_index)
            store.set(KEY_STAGE_NAME, stage.name)
            store.set(KEY_STAGE_TOTAL, stage_total)
            store.set(KEY_STAGE_STATUS, "running")

    def _record_stage_event(
        self, solver: Any, stage: StageSpec, stage_index: int, kind: str
    ) -> None:
        store = getattr(solver, "context_store", None)
        if store is not None and callable(getattr(store, "set", None)):
            store.set(KEY_STAGE_STATUS, kind.replace("stage_", ""))
        if store is not None and callable(getattr(store, "to_dict", None)):
            try:
                ctx = dict(store.to_dict() or {})
            except Exception:
                ctx = {}
        else:
            ctx = {}
        record_context_event(
            ctx,
            kind=kind,
            key=KEY_STAGE_NAME,
            value={KEY_STAGE_INDEX: stage_index, KEY_STAGE_NAME: stage.name},
            source=f"StageRunner[{stage.name}]",
            step=stage_index,
        )

    # -- result collection ------------------------------------------------

    def _merge_results(self) -> Dict[str, Any]:
        return {
            "stages": [
                {
                    "name": r["stage_name"],
                    "index": r["stage_index"],
                    "elapsed_sec": r["elapsed_sec"],
                    "artifacts": r["produced_artifacts"],
                }
                for r in self._results
            ],
            "stage_count": len(self._results),
            "artifact_registry": {
                k: _ref_to_dict(v) for k, v in self._artifact_registry.items()
            },
        }


# ────────────────────────────────────────────────────────────────────────
# SerialStageSolver — SolverBase-compatible wrapper
# ────────────────────────────────────────────────────────────────────────


class SerialStageSolver:
    """Wraps a StageRunner inside a SolverBase-compatible surface.

    Runs all stages inside :meth:`run`.  The object is deliberately NOT a
    SolverBase subclass so it can live in ``core/`` without pulling in the
    full SolverBase constructor surface.  To nest it inside an outer solver
    use :class:`~nsgablack.core.nested_solver.InnerRuntimeEvaluator` with a
    ``solver_factory`` that returns a SerialStageSolver.
    """

    def __init__(
        self,
        stages: List[StageSpec],
        *,
        name: str = "SerialStageSolver",
        artifact_registry: Optional[Dict[str, ArtifactRef]] = None,
        context_store: Optional[Any] = None,
        snapshot_store: Optional[Any] = None,
        strict: bool = False,
        accepted_parent_contracts: Optional[tuple[str, ...]] = None,
    ) -> None:
        self._stages = list(stages)
        self.name = str(name)
        self._artifact_registry = dict(artifact_registry or {})
        self.context_store = context_store
        self.snapshot_store = snapshot_store
        self._strict = bool(strict)
        self.accepted_parent_contracts = tuple(
            accepted_parent_contracts or ("outer.default",)
        )
        self._runner: Optional[StageRunner] = None
        self._merged: Optional[Dict[str, Any]] = None
        self.generation = 0
        self.step_count = 0
        self.stop_requested = False
        self.running = False

    def setup(self) -> None:
        self._runner = StageRunner(
            stages=self._stages,
            artifact_registry=self._artifact_registry,
            context_store=self.context_store,
            snapshot_store=self.snapshot_store,
            global_metadata={"solver_name": self.name},
            strict=self._strict,
        )

    def step(self) -> None:
        self.step_count += 1

    def teardown(self) -> None:
        if self._runner is not None and self.context_store is not None:
            store = self.context_store
            if callable(getattr(store, "set", None)):
                summary = {
                    k: _ref_to_dict(v) for k, v in self._runner.artifact_registry.items()
                }
                store.set("stage_artifact_registry", summary)

    def run(
        self,
        max_steps: Optional[int] = None,
        return_dict: bool = False,
    ) -> Any:
        self.running = True
        try:
            self.setup()
            self._merged = self._runner.run() if self._runner is not None else {}
            self._merged["name"] = self.name
        finally:
            self.teardown()
            self.running = False
        return self._merged if return_dict else self._merged

    # -- InnerRuntimeEvaluator compat ------------------------------------

    def request_stop(self) -> None:
        self.stop_requested = True

    def build_context(self, extra: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        ctx: Dict[str, Any] = {KEY_STEP: self.step_count}
        if self.context_store is not None and callable(
            getattr(self.context_store, "to_dict", None)
        ):
            ctx.update(dict(self.context_store.to_dict() or {}))
        if extra:
            ctx.update(dict(extra))
        return ctx

    def get_context(self) -> Dict[str, Any]:
        return self.build_context()

    # -- result accessors ------------------------------------------------

    def get_artifact(self, key: str) -> Optional[ArtifactRef]:
        if self._runner is not None:
            return self._runner.get_artifact(key)
        return None

    @property
    def artifact_registry(self) -> Dict[str, ArtifactRef]:
        if self._runner is not None:
            return self._runner.artifact_registry
        return dict(self._artifact_registry)

    @property
    def results(self) -> List[Dict[str, Any]]:
        if self._runner is not None:
            return self._runner.results
        return []
