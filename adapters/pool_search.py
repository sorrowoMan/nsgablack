"""Pool-driven search decisions using the existing Solver execution substrate."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence
import numpy as np

from .algorithm_adapter import AlgorithmAdapter, CompositeAdapter, subset_adapter_feedback
from .strategy_task import StrategyOrigin, StrategyTask, attach_strategy_origin
from nsgablack.context_keys import (
    KEY_PHASE, KEY_TASK, KEY_SOLUTION_INPUT_REF, KEY_SOLUTION_INPUT_MODE,
    KEY_SOLUTION_POOL_REF, KEY_SOLUTION_POOL_TIME,
)


@dataclass(frozen=True)
class PoolSearchSpec:
    """Initial pool intake quota, independent of the Adapter's member capacity."""

    adapter: AlgorithmAdapter
    initial_count: int

    def __post_init__(self):
        if not isinstance(self.adapter, AlgorithmAdapter):
            raise TypeError("pool search requires AlgorithmAdapter instances")
        if type(self.initial_count) is not int or self.initial_count <= 0:
            raise ValueError("pool search initial count must be positive")
        if not {"initialize", "compete"}.issubset(self.adapter.pool_input_modes):
            raise ValueError(f"{self.adapter.name} must declare initialize and compete pool inputs")


class PoolSearchAdapter(CompositeAdapter):
    """Prepare solutions, run private populations, trigger a recovery trajectory.

    Initial allocations are disjoint by record position and do not limit the
    pool or prescribe child Unit sizes. Recovery seeds default
    to the latest published candidate; a selection callable can replace this.
    Stagnation defaults to min(sum(raw objectives) + 1e6*raw violation), or uses
    a supplied metric. Returning candidates undergo normal reevaluation and
    receiving population selection, including its own preference projection.
    """
    context_requires = (KEY_SOLUTION_POOL_TIME,)
    context_provides = (KEY_PHASE, KEY_TASK, KEY_SOLUTION_INPUT_REF, KEY_SOLUTION_INPUT_MODE)
    context_optional = (KEY_SOLUTION_POOL_REF,)
    context_notes = "Pool prepare/search/recovery/return; explicit timestamped inputs and private child Units."
    state_recovery_notes = "Restores phase, pool input references, stagnation and private child Units."
    state_recovery_level = "L2"
    population_state_mode = "partitioned"

    def __init__(self, producer: AlgorithmAdapter, searches: Sequence[PoolSearchSpec], *,
                 stagnation_steps=20, recovery_steps=5, restart_recovery=True,
                 metric: Callable | None = None, recovery_selector: Callable | None = None,
                 name="pool_search", priority=0):
        specs = tuple(searches)
        if not isinstance(producer, AlgorithmAdapter) or not specs:
            raise ValueError("pool search requires a producer and searchers")
        if any(not isinstance(s, PoolSearchSpec) for s in specs):
            raise TypeError("searches must contain PoolSearchSpec")
        if any(type(v) is not int or v <= 0 for v in (stagnation_steps, recovery_steps)):
            raise ValueError("pool scheduling step limits must be positive")
        children = [producer, *(s.adapter for s in specs)]
        if len({id(c) for c in children}) != len(children) or len({c.name for c in children}) != len(children):
            raise ValueError("pool search requires distinct child instances and names")
        if restart_recovery and (not producer.supports_pool_restart or "initialize" not in producer.pool_input_modes):
            raise ValueError("producer must declare pool initialization and an explicit search restart")
        if (metric is not None and not callable(metric)) or (recovery_selector is not None and not callable(recovery_selector)):
            raise TypeError("pool selectors and metrics must be callable")
        super().__init__(children, name=name, priority=priority)
        self.producer, self.searches = producer, specs
        self.stagnation_steps, self.recovery_steps = stagnation_steps, recovery_steps
        self.restart_recovery = bool(restart_recovery)
        self.metric, self.recovery_selector = metric, recovery_selector
        self._reset_local()

    def _reset_local(self):
        self.phase = "preparing"
        self.prepared_count = self.recovery_count = self.stagnation = 0
        self.best_metric = None
        self.input_ids, self._frames = {}, {}
        self.ready_stamp = self.recovery_start = None
        self._recovery_started = False
        self._owner_path = None

    def setup(self, control):
        self._reset_local()
        control.solution_pool.checkpoint_required = True
        super().setup(control)

    def get_population_partitions(self):
        # Waiting, uninitialized searchers have no population authority yet.
        return tuple(p for p in super().get_population_partitions() if len(p.population))

    def resolve_population_state_mode(self):
        return "partitioned" if self.get_population_partitions() else "none"

    def _source_refs(self, control, *, at=None):
        pool = control.solution_pool
        if control.adapter is self:
            return pool.select(at=at, source=self.name)
        refs = pool.select(at=at)
        if not refs:
            return ()
        states = pool.read(refs).semantic_states
        return tuple(ref for ref, state in zip(refs, states)
                     if any(origin.owner_path[:len(self._owner_path)] == self._owner_path
                            for origin in StrategyOrigin.from_candidate(state)))

    def _prepare_inputs(self, control):
        if self.input_ids:
            return
        pool = control.solution_pool
        self.ready_stamp = pool.timestamp.as_dict()
        refs = self._source_refs(control, at=pool.timestamp)
        required = sum(s.initial_count for s in self.searches)
        if len(refs) < required:
            raise ValueError("producer has not published enough pool candidates")
        start = 0
        for spec in self.searches:
            end = start + spec.initial_count
            self.input_ids[spec.adapter.name] = pool.bind_input(refs[start:end])
            start = end

    def _active(self, control):
        if self.phase == "preparing":
            return (self.producer,)
        if self.phase == "search":
            self._prepare_inputs(control)
            return tuple(s.adapter for s in self.searches)
        if self.phase == "recovery":
            if not self._recovery_started:
                pool = control.solution_pool
                self.recovery_start = pool.timestamp.as_dict()
                if self.restart_recovery:
                    refs = (tuple(self.recovery_selector(pool, pool.timestamp)) if self.recovery_selector
                            else self._source_refs(control, at=pool.timestamp)[-1:])
                    if len(refs) != 1:
                        raise ValueError("single-trajectory recovery requires one explicit seed")
                    self.input_ids[self.producer.name] = pool.bind_input(refs)
                    self.producer.restart_search(control, {})
                self._recovery_started = True
            return (self.producer,)
        if self.phase == "return":
            return tuple(s.adapter for s in self.searches)
        raise ValueError("unknown pool search phase")

    def _context_for(self, child, context):
        frame = self._frames[child.name]
        local = StrategyTask.from_dict(frame[KEY_TASK]).bind(context)
        for key in (KEY_SOLUTION_INPUT_REF, KEY_SOLUTION_INPUT_MODE):
            local.pop(key, None)
            if key in frame:
                local[key] = frame[key]
        for key in (KEY_SOLUTION_POOL_REF, KEY_SOLUTION_POOL_TIME):
            local[key] = frame[key]
        return local

    def propose(self, control, context):
        parent = StrategyTask.from_context(context) if context.get(KEY_TASK) is not None else None
        self._owner_path = parent.owner_path if parent else (self.name,)
        active = self._active(control)
        out = []
        self._last_ranges, self._frames = [], {}
        if self.phase == "return":
            returned = tuple(r for r in self._source_refs(control)
                             if control.solution_pool.stamp_for(r).sequence > self.recovery_start["sequence"])
            if not returned:
                raise ValueError("recovery published no candidate for population competition")
        for child in active:
            index = self.adapters.index(child)
            budget = (int(getattr(getattr(child, "cfg", None), "batch_size", 1)) if child is self.producer
                      else next(s.initial_count for s in self.searches if s.adapter is child))
            if (self.phase == "search" and child is not self.producer and
                    control.solution_pool.input_remaining(self.input_ids[child.name]) == 0):
                budget = max(1, int(getattr(getattr(child, "cfg", None), "offspring_size", budget)))
            if self.phase == "return":
                budget = len(returned)
            task = StrategyTask(
                owner_path=(*self._owner_path, child.name),
                role=child.name, unit_id=index, role_index=index,
                adapter_name=child.name, step=int(control.generation), phase=self.phase,
                phase_step=self.recovery_count if self.phase == "recovery" else self.prepared_count,
                budget=budget, parent_task_id=None if parent is None else parent.task_id,
            )
            frame = {KEY_TASK: task.as_dict(),
                     KEY_SOLUTION_POOL_REF: context.get(KEY_SOLUTION_POOL_REF),
                     KEY_SOLUTION_POOL_TIME: context[KEY_SOLUTION_POOL_TIME]}
            if self.phase == "return":
                frame[KEY_SOLUTION_INPUT_REF] = control.solution_pool.bind_input(returned)
                frame[KEY_SOLUTION_INPUT_MODE] = "compete"
            elif child.name in self.input_ids:
                frame[KEY_SOLUTION_INPUT_REF] = self.input_ids[child.name]
                frame[KEY_SOLUTION_INPUT_MODE] = "initialize"
            self._frames[child.name] = frame
            begin = len(out)
            key = frame.get(KEY_SOLUTION_INPUT_REF)
            remaining = None if key is None else control.solution_pool.input_remaining(key)
            values = self.coerce_candidates(child.propose(control, self._context_for(child, context)))
            if len(values) > budget:
                raise ValueError("pool child exceeded its declared proposal budget")
            frame["intake_count"] = 0 if key is None else remaining - control.solution_pool.input_remaining(key)
            if frame["intake_count"] not in (0, len(values)):
                raise ValueError("pool child must not mix intake seeds and generated proposals")
            out.extend(attach_strategy_origin(value, task, i, control) for i, value in enumerate(values))
            self._last_ranges.append((child, begin, len(out)))
        return out

    def _proposal_contexts(self, proposed_count, context):
        return tuple(c for child, start, end in self._last_ranges
                     for c in child.get_proposal_contexts(end-start, self._context_for(child, context)))

    def proposal_repair_children(self, repair, context):
        return tuple((child, repair.for_range(start, end), self._context_for(child, context))
                     for child, start, end in self._last_ranges)

    def on_proposal_disposition(self, control, disposition, context):
        ranges, cursor = [], 0
        for child, start, end in self._last_ranges:
            local = disposition.for_range(start, end)
            child.on_proposal_disposition(control, local, self._context_for(child, context))
            frame = self._frames[child.name]
            if frame["intake_count"]:
                control.solution_pool.settle_input(frame[KEY_SOLUTION_INPUT_REF], frame["intake_count"],
                                                   local.accepted_indices)
            if local.accepted_count:
                ranges.append((child, cursor, cursor+local.accepted_count))
                cursor += local.accepted_count
        self._last_ranges = ranges

    def update(self, control, candidates, feedback, context):
        expected = sum(end-start for _, start, end in self._last_ranges)
        if len(candidates) != expected or feedback.candidate_count != expected:
            raise ValueError("pool feedback does not match original child proposals")
        for child, start, end in self._last_ranges:
            child.update(control, candidates[start:end], subset_adapter_feedback(feedback, slice(start,end)),
                         self._context_for(child, context))
        if self.phase == "preparing":
            self.prepared_count += len(candidates)
            if self.prepared_count >= sum(s.initial_count for s in self.searches):
                self.phase = "search"
        elif self.phase == "search":
            if any(control.solution_pool.input_remaining(self.input_ids[s.adapter.name]) for s in self.searches):
                return  # Complete partial initialization before measuring stagnation.
            value = (float(self.metric(feedback)) if self.metric else
                     float(np.min(np.sum(feedback.raw_objectives, axis=1) + 1e6*feedback.raw_violations)))
            if not np.isfinite(value):
                raise ValueError("pool stagnation metric must be finite")
            if self.best_metric is None or value < self.best_metric:
                self.best_metric, self.stagnation = value, 0
            else:
                self.stagnation += 1
            if self.stagnation >= self.stagnation_steps:
                self.phase, self.recovery_count, self._recovery_started = "recovery", 0, False
        elif self.phase == "recovery":
            self.recovery_count += 1
            if self.recovery_count >= self.recovery_steps:
                self.phase = "return"
        elif self.phase == "return":
            self.phase, self.stagnation = "search", 0

    def _local_state(self):
        return dict(phase=self.phase, prepared_count=self.prepared_count,
                    recovery_count=self.recovery_count, stagnation=self.stagnation,
                    best_metric=self.best_metric, input_ids=dict(self.input_ids),
                    ready_stamp=self.ready_stamp, recovery_start=self.recovery_start,
                    recovery_started=self._recovery_started,
                    owner_path=self._owner_path,
                    frames={k: dict(v) for k,v in self._frames.items()})

    def _restore_local(self, state):
        if state["phase"] not in {"preparing", "search", "recovery", "return"}:
            raise ValueError("unknown pool search checkpoint phase")
        self.phase = state["phase"]
        for name in ("prepared_count", "recovery_count", "stagnation", "best_metric", "ready_stamp", "recovery_start"):
            setattr(self, name, state[name])
        self.input_ids, self._frames = dict(state["input_ids"]), dict(state["frames"])
        self._recovery_started = state["recovery_started"]
        self._owner_path = None if state["owner_path"] is None else tuple(state["owner_path"])

    def snapshot_step_state(self):
        return {**super().snapshot_step_state(), "pool_search": self._local_state()}

    def restore_step_state(self, state):
        super().restore_step_state(state)
        self._restore_local(state["pool_search"])

    def get_state(self):
        return {**super().get_state(), "pool_search": self._local_state(), "pool_plan": self.checkpoint_identity()}

    def set_state(self, state):
        if state["pool_plan"] != self.checkpoint_identity():
            raise ValueError("pool search checkpoint plan changed")
        super().set_state(state)
        self._restore_local(state["pool_search"])

    def checkpoint_identity(self):
        def identity(fn):
            return None if fn is None else f"{fn.__module__}.{fn.__qualname__}"
        return dict(initial_counts=[s.initial_count for s in self.searches],
                    stagnation_steps=self.stagnation_steps, recovery_steps=self.recovery_steps,
                    restart_recovery=self.restart_recovery, metric=identity(self.metric),
                    recovery_selector=identity(self.recovery_selector))

    def get_runtime_context_projection(self, solver):
        return {KEY_PHASE: self.phase}

    def get_runtime_context_projection_sources(self, solver):
        return {KEY_PHASE: f"adapter.{type(self).__name__}"}


__all__ = ["PoolSearchAdapter", "PoolSearchSpec"]
