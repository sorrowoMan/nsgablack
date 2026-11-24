"""Structured local search schedules hosted by the existing strategy Router.

BlackBase owns the pure execution cursor. This Adapter owns optimization
instances, normal proposal routing and pool inputs; it never starts a Solver,
thread, resource grant or independent publication transaction.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Callable, Mapping

import numpy as np
from blackbase.orchestration import ExecutionPlan, ExecutionCursor, LeafProgress

from .empty_outcome import child_empty_proposal_outcome
from .multi_strategy import MultiStrategyConfig, StrategyRouterAdapter, StrategySpec
from .multi_strategy.adapter import StrategyInstanceSpec
from .pool_tasks import PoolTaskAdapter, _callable_id
from ..core.state.step_outcome import StepOutcome


stage = ExecutionPlan.leaf
serial = ExecutionPlan.serial
multi = ExecutionPlan.multi


def repeat(*, times: int, body: ExecutionPlan) -> ExecutionPlan:
    """Reopen local quotas, retaining the uniquely owned algorithm instances."""
    return ExecutionPlan.repeat(body, count=times)


@dataclass(frozen=True)
class SearchProgress:
    """One activation's accepted updates; siblings and idle attempts add none."""
    name: str
    label: str
    activation_id: str
    updates: int
    last_metric: float | None
    best_metric: float | None
    stagnant_updates: int


class _PlanPoolTaskAdapter(PoolTaskAdapter):
    # A scheduling implementation of the public PoolTask component, rather
    # than a separately selectable user component in Catalog.
    catalog_owner_type = PoolTaskAdapter

    def __init__(self, *args, plan_owner, **kwargs):
        self._plan_owner = plan_owner
        super().__init__(*args, **kwargs)

    def _request_key(self, control, context):
        # Initialize once remains initialize once, including later activations.
        if self.spec.mode == "initialize":
            return super()._request_key(control, context)
        activation = self._plan_owner._activation(self.role)
        key = self._plan_owner._scoped_activation_id(activation.activation_id)
        if self.spec.request_key is not None:
            suffix = super()._request_key(control, context)
            if not isinstance(suffix, str) or not suffix:
                raise ValueError("pool task request key must be a nonempty string")
            key = f"{key}/{suffix}"
        return key

    def propose(self, control, context):
        activation = self._plan_owner._activation(self.role)
        enabled = not self.spec.phases or activation.label in self.spec.phases
        if (enabled and activation.steps is None
                and self.spec.mode in {"initialize", "compete"}):
            # A completed task is local completion here. PoolTask's ordinary
            # Router behavior may otherwise fall through into fresh search.
            self._local["passthrough"] = False
            self._start_request(control, context)
            if self._local.get("status") == "done":
                return []
        return super().propose(control, context)


class SearchPlanAdapter(StrategyRouterAdapter):
    """Run nested serial/multi/repeat without global-step arithmetic.

    A plan leaf refers to one StrategySpec.name; serial occurrences reuse that
    algorithm. ``steps`` counts this leaf's nonempty accepted updates. Omit it
    to wait for a bounded PoolTask or an algorithm's local completion. ``until``
    maps leaf labels to pure named functions receiving SearchProgress. Optional
    ``metrics`` map the same labels to named feedback->finite scalar functions;
    lower is better. No multiobjective aggregation is inferred for conditions.
    """
    state_recovery_notes = (
        "Restores shared execution cursor, activation observations, frozen pool tasks "
        "and uniquely owned strategy instances through the existing Router."
    )

    def __init__(self, plan: ExecutionPlan, strategies, *, config=None,
                 working_pool=None, until: Mapping[str, Callable] | None = None,
                 metrics: Mapping[str, Callable] | None = None,
                 name="search_plan", priority=0):
        if not isinstance(plan, ExecutionPlan):
            raise TypeError("search plan must be an ExecutionPlan")
        self._plan = plan
        self.cursor = ExecutionCursor(plan)
        self.until = MappingProxyType(dict(until or {}))
        self.metrics = MappingProxyType(dict(metrics or {}))
        self._observations = {}
        self._proposal_activations = {}
        self._stop_outcome = None
        self._dispatch_offset = 0
        self._parent_activation = None
        self._execution_scope = None
        specs = list(strategies)
        if any(not isinstance(spec, StrategySpec) for spec in specs):
            raise TypeError("search plan strategies must be StrategySpec instances")
        names = [spec.name for spec in specs]
        if len(set(names)) != len(names) or set(names) != set(plan.owner_names):
            raise ValueError("plan owners and unique strategy names must match exactly")
        if any(not spec.enabled or spec.weight <= 0 for spec in specs):
            raise ValueError("plan owners must be enabled with positive weights")
        self._leaf_nodes = tuple(self._leaves(plan))
        labels = {leaf.label for leaf in self._leaf_nodes}
        for callbacks in (self.until, self.metrics):
            if set(callbacks).difference(labels):
                raise ValueError("condition/metric references an unknown plan label")
            for function in callbacks.values():
                if not callable(function):
                    raise TypeError("plan conditions and metrics must be named functions")
                _callable_id(function)
        by_name = {spec.name: spec for spec in specs}
        for leaf in self._leaf_nodes:
            task = by_name[leaf.name].pool_task
            uses_task = task is not None and (not task.phases or leaf.label in task.phases)
            if uses_task and leaf.steps != 0:
                if leaf.label in self.until:
                    raise ValueError("pool task stages wait for completion; until cannot abandon a running request")
                if task.mode in {"refine", "compete"} and leaf.steps is not None:
                    raise ValueError("refine/compete plan stages omit steps and wait for task completion")
        cfg = config or MultiStrategyConfig(adapt_weights=False,
            phase_schedule=(("plan", -1),))
        if (cfg.phase_policy is not None or cfg.phase_roles is not None
                or cfg.control_rules or cfg.role_enable_policy is not None):
            raise ValueError("SearchPlanAdapter owns phase/role scheduling; use plan/until")
        super().__init__(strategies=specs, config=cfg, name=name,
                         priority=priority, working_pool=working_pool)

    @staticmethod
    def _leaves(node):
        if node.kind == "leaf":
            yield node
        else:
            for child in node.children:
                yield from SearchPlanAdapter._leaves(child)

    @property
    def plan(self):
        return self._plan

    def _build_units(self):
        units = []
        for index, spec in enumerate(self.strategies):
            adapter = spec.adapter
            if spec.pool_task is not None:
                adapter = _PlanPoolTaskAdapter(adapter, spec.pool_task, role=spec.name,
                    namespace=self.name, plan_owner=self)
            units.append(StrategyInstanceSpec(spec.name, index, adapter))
        return self._validate_instances(units)

    def setup(self, control):
        self.cursor = ExecutionCursor(self.plan)
        self._observations = {}
        self._proposal_activations = {}
        self._stop_outcome = None
        self._dispatch_offset = 0
        self._parent_activation = None
        self._execution_scope = None
        super().setup(control)

    def on_schedule_activation(self, control, activation_id):
        # The local cursor, rather than Router's transparent fanout, decides
        # which child activation is entering. Inactive branches stay untouched.
        from .algorithm_adapter import AlgorithmAdapter
        AlgorithmAdapter.on_schedule_activation(self, control, activation_id)
        if activation_id == self._parent_activation:
            return
        if self._parent_activation is None or self.cursor.completed:
            self._execution_scope = activation_id
            if self.cursor.completed:
                self.cursor = ExecutionCursor(self.plan)
                self._observations = {}
                self._clear_dispatch()
                self._stop_outcome = None
                self._dispatch_offset = 0
        # A quota may pause an unfinished child. Its frozen task and execution
        # scope survive a later parent slice instead of silently restarting it.
        self._parent_activation = activation_id

    def _scoped_activation_id(self, identity):
        return identity if self._execution_scope is None else f"{self._execution_scope}/{identity}"

    def _activation(self, name):
        for activation in self.cursor.active():
            if activation.name == name:
                return activation
        raise RuntimeError(f"strategy {name!r} has no active plan position")

    def _phase_for_step(self, step):
        return "plan", int(step)

    def _enabled_roles_for_phase(self, phase):
        return {activation.name for activation in self.cursor.active()}

    def _allocate_role_budgets(self, policy_ctx=None, rule_effects=None):
        active = [item.name for item in self.cursor.active()]
        capacity = max(1, int(self.cfg.total_batch_size))
        if len(active) > capacity:
            # Candidate capacity must not starve a waiting parallel sibling.
            start = self._dispatch_offset % len(active)
            selected = (active + active)[start:start + capacity]
            self._dispatch_offset = (start + capacity) % len(active)
            return {name: 1 for name in selected}
        return super()._allocate_role_budgets(policy_ctx, rule_effects)

    def _prepare_strategy_task(self, unit, task):
        activation = self._activation(unit.role)
        # Timing alone must not smuggle the Router's heuristic global-best
        # seeds into a different algorithm. Candidate handoff uses PoolTask.
        return replace(task, phase=activation.label, phase_step=activation.count, seeds=())

    def _prune_observations(self):
        active = {item.activation_id for item in self.cursor.active()}
        self._observations = {key: value for key, value in self._observations.items() if key in active}

    def _fold_conditions(self):
        changes = []
        for activation in self.cursor.active():
            condition = self.until.get(activation.label)
            observation = self._observations.get(activation.activation_id)
            if (condition is None or observation is None
                    or observation["checked"] == activation.count):
                continue
            progress = SearchProgress(activation.name, activation.label,
                activation.activation_id, activation.count, observation["last"],
                observation["best"], observation["stagnant"])
            result = condition(progress)
            if not isinstance(result, (bool, np.bool_)):
                raise TypeError("plan until must return bool")
            observation["checked"] = activation.count
            if result:
                changes.append(LeafProgress(activation.activation_id,
                                            completed=True, reason="condition"))
        if changes:
            self.cursor.advance(changes)
            self._prune_observations()
        return bool(changes)

    def _clear_dispatch(self):
        self._last_allocations = []
        self._unit_tasks = {}
        self._unit_proposal_contexts = {}
        self._unit_base_dispositions = {}
        self._proposal_activations = {}

    def propose(self, control, context):
        self._stop_outcome = None
        # Only scheduling transitions fold here. Pool writes still belong to
        # the existing leaf update/selection transaction, never to idle commits.
        for _ in range(1024):
            if getattr(control, "stop_requested", False):
                self._clear_dispatch()
                self._stop_outcome = StepOutcome(status="cancelled", reason="stop_requested")
                return []
            if self._fold_conditions():
                continue
            if self.cursor.completed:
                self._clear_dispatch()
                return []
            active = {item.name: item for item in self.cursor.active()}
            for unit in self.units:
                if unit.role in active:
                    unit.adapter.on_schedule_activation(control,
                        self._scoped_activation_id(active[unit.role].activation_id))
            candidates = super().propose(control, context)
            if self._dispatch_stop_outcome is not None:
                self._stop_outcome = self._dispatch_stop_outcome
                self._clear_dispatch()
                return []
            allocated = {(role, uid) for role, uid, _start, _end in self._last_allocations}
            self._proposal_activations = {
                key: active[key[0]].activation_id for key in allocated}
            changes = []
            for unit in self.units:
                key = (unit.role, int(unit.unit_id))
                if key not in self._unit_proposal_contexts or key in allocated:
                    continue
                ctx = self._unit_proposal_contexts[key]
                outcome = child_empty_proposal_outcome(unit.adapter, control, ctx)
                task = unit.adapter if isinstance(unit.adapter, PoolTaskAdapter) else None
                is_task = task is not None and not task._local.get("passthrough")
                if outcome is not None and (outcome.status == "cancelled" or outcome.stop_requested):
                    if candidates:
                        from blackbase.contracts import BatchDisposition
                        self.on_proposal_disposition(control, BatchDisposition.prefix(
                            proposed_count=len(candidates), accepted_count=0,
                            reason="sibling_cancelled"), context)
                    self._stop_outcome = outcome
                    self._clear_dispatch()
                    return []
                if (is_task and task.task_status["status"] == "done"
                        or outcome is not None and outcome.terminal):
                    changes.append(LeafProgress(active[unit.role].activation_id,
                        completed=True, reason="task_done" if is_task else outcome.reason))
            if changes:
                self.cursor.advance(changes)
                self._prune_observations()
                if not candidates:
                    continue
            return candidates
        raise RuntimeError("search plan exceeded bounded control traversal without work")

    def get_empty_proposal_outcome(self, control, context):
        if self._stop_outcome is not None:
            return self._stop_outcome
        if self.cursor.completed:
            return StepOutcome(status="terminal", reason="search_plan_completed",
                               metadata={"completion": "completed"})
        return StepOutcome(status="idle", reason="search_plan_waiting")

    def get_pool_task_results(self, control, role):
        """Read this owner's current completed refinement, excluding old requests."""
        for unit in self.units:
            if unit.role == role:
                if not isinstance(unit.adapter, PoolTaskAdapter):
                    raise ValueError(f"strategy {role!r} has no PoolTask")
                return unit.adapter.get_pool_task_results(control)
        raise KeyError(f"unknown search plan strategy: {role}")

    def update(self, control, candidates, feedback, context):
        allocations = list(self._last_allocations)
        activations = dict(self._proposal_activations)
        super().update(control, candidates, feedback, context)
        changes = []
        by_key = {(unit.role, int(unit.unit_id)): unit for unit in self.units}
        for role, uid, start, end in allocations:
            if start == end:
                continue
            key = (role, uid)
            activation_id = activations[key]
            activation = next(item for item in self.cursor.active()
                              if item.activation_id == activation_id)
            observation = self._observations.setdefault(activation_id,
                {"best": None, "last": None, "stagnant": 0, "checked": -1})
            metric = self.metrics.get(activation.label)
            if metric is not None:
                from .algorithm_adapter import subset_adapter_feedback
                value = float(metric(subset_adapter_feedback(feedback, slice(start, end))))
                if not np.isfinite(value):
                    raise ValueError("plan metric must be finite")
                observation["last"] = value
                if observation["best"] is None or value < observation["best"]:
                    observation["best"], observation["stagnant"] = value, 0
                else:
                    observation["stagnant"] += 1
            adapter = by_key[key].adapter
            if (isinstance(adapter, PoolTaskAdapter) and not adapter._local.get("passthrough")
                    and adapter.task_status["status"] == "running"
                    and activation.steps is not None and activation.count + 1 >= activation.steps):
                raise ValueError("stage quota would abandon unfinished pool initialization; omit steps")
            done = (activation.steps is None and isinstance(adapter, PoolTaskAdapter)
                    and not adapter._local.get("passthrough")
                    and adapter.task_status["status"] == "done")
            changes.append(LeafProgress(activation_id, steps=1, completed=done,
                                       reason="task_done" if done else ""))
        if changes:
            self.cursor.advance(changes)
            self._prune_observations()
        self._proposal_activations = {}

    def _plan_identity(self):
        return {"plan": self.plan.fingerprint,
                "until": {key: self._policy_declaration(fn) for key, fn in self.until.items()},
                "metrics": {key: self._policy_declaration(fn) for key, fn in self.metrics.items()}}

    def validate_search_plan_contract(self):
        """Inspect declarations/control values without constructing any Unit."""
        if not isinstance(self.cursor, ExecutionCursor):
            raise TypeError("search plan requires an ExecutionCursor")
        if {spec.name for spec in self.strategies} != set(self.plan.owner_names):
            raise ValueError("search plan strategy owners changed after assembly")
        self._validated_plan_state(self._plan_state())

    def _plan_state(self):
        return {"identity": self._plan_identity(), "cursor": self.cursor.get_state(),
                "observations": copy.deepcopy(self._observations),
                "dispatch_offset": self._dispatch_offset,
                "parent_activation": self._parent_activation,
                "execution_scope": self._execution_scope,
                "proposals": [dict(role=role, unit_id=uid, activation_id=identity)
                    for (role, uid), identity in self._proposal_activations.items()]}

    def _validated_plan_state(self, state):
        if not isinstance(state, Mapping) or state.get("identity") != self._plan_identity():
            raise ValueError("search plan checkpoint identity mismatch")
        if set(state) != {"identity", "cursor", "observations", "dispatch_offset", "proposals",
                          "parent_activation", "execution_scope"}:
            raise ValueError("search plan checkpoint fields mismatch")
        parent, scope = state["parent_activation"], state["execution_scope"]
        if (any(value is not None and (not isinstance(value, str) or not value)
                for value in (parent, scope)) or (parent is None) != (scope is None)):
            raise ValueError("invalid search plan parent activation scope")
        cursor = ExecutionCursor(self.plan)
        cursor.set_state(state["cursor"])
        offset = state.get("dispatch_offset")
        if type(offset) is not int or offset < 0:
            raise ValueError("invalid search plan dispatch offset")
        active = {item.activation_id: item for item in cursor.active()}
        observations = copy.deepcopy(state["observations"])
        if not isinstance(observations, dict) or set(observations).difference(active):
            raise ValueError("search plan observations do not match active positions")
        for identity, row in observations.items():
            if (set(row) != {"best", "last", "stagnant", "checked"}
                    or type(row["stagnant"]) is not int or not 0 <= row["stagnant"] <= active[identity].count
                    or type(row["checked"]) is not int or not -1 <= row["checked"] <= active[identity].count
                    or any(value is not None and not np.isfinite(float(value))
                           for value in (row["best"], row["last"]))):
                raise ValueError("invalid search plan progress observation")
        proposals = {}
        expected = {(spec.name, index) for index, spec in enumerate(self.strategies)}
        for row in state["proposals"]:
            key = (row["role"], row["unit_id"])
            if (type(row["unit_id"]) is not int or key not in expected
                    or key in proposals or row["activation_id"] not in active):
                raise ValueError("invalid search plan proposal activation")
            if active[row["activation_id"]].name != key[0]:
                raise ValueError("search plan proposal owner mismatch")
            proposals[key] = row["activation_id"]
        return cursor, observations, proposals, offset, parent, scope

    def _apply_plan_state(self, parsed):
        (self.cursor, self._observations, self._proposal_activations, self._dispatch_offset,
         self._parent_activation, self._execution_scope) = parsed
        self._stop_outcome = self._dispatch_stop_outcome

    def get_state(self):
        return {**super().get_state(), "search_plan": self._plan_state()}

    def set_state(self, state):
        parsed = self._validated_plan_state(state.get("search_plan"))
        super().set_state(state)
        self._apply_plan_state(parsed)

    def snapshot_step_state(self):
        return {**super().snapshot_step_state(), "search_plan": self._plan_state()}

    def restore_step_state(self, state):
        parsed = self._validated_plan_state(state.get("search_plan"))
        super().restore_step_state(state)
        self._apply_plan_state(parsed)

    def teardown(self, control):
        # A paused/finished branch is kept alive until the unique owner ends.
        from blackbase.project import attach_failure_evidence
        failures = []
        for unit in self.units:
            try:
                unit.adapter.teardown(control)
            except BaseException as exc:
                failures.append((unit.role, exc))
        if failures:
            error = failures[0][1]
            attach_failure_evidence(error, "search_plan_teardown", tuple(
                {"participant": role, "error_type": type(exc).__name__, "message": str(exc)}
                for role, exc in failures))
            raise error


__all__ = ["SearchPlanAdapter", "SearchProgress", "ExecutionPlan", "stage", "serial", "multi", "repeat"]
