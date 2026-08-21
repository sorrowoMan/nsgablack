"""
Role-based adapter composition for multi-role / multi-agent style optimization.

Design goals:
- Keep solver bases unchanged: orchestration lives in adapters/plugins.
- Allow "algorithm role-ization": wrap any AlgorithmAdapter as a role.
- Support nested composition: a controller adapter can hold multiple role adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
import warnings

import numpy as np
from blackbase.contracts import BatchDisposition
from blackbase.context import RuntimeContextProjection

from ..algorithm_adapter import (
    AlgorithmAdapter,
    PopulationPartition,
    prefixed_population_partitions,
    restore_prefixed_population_partitions,
    subset_adapter_feedback,
)
from ..runtime_projection import aggregate_adapter_runtime_projections
from blackbase.context.context_keys import (
    KEY_CANDIDATE_ROLES,
    KEY_ROLE,
    KEY_ROLE_ADAPTER,
    KEY_ROLE_INDEX,
    KEY_ROLE_REPORTS,
    KEY_STEP,
)


@dataclass
class RoleAdapter(AlgorithmAdapter):
    """Wrap an adapter with role metadata and optional candidate limiting."""

    role: str = "role"
    inner: Optional[AlgorithmAdapter] = None
    max_candidates: Optional[int] = None
    companions: Tuple[str, ...] = ()
    recommended_suite: Optional[str] = None
    strict_contract: bool = False
    context_requires: Tuple[str, ...] = ()
    context_provides: Tuple[str, ...] = (KEY_ROLE, KEY_ROLE_ADAPTER)
    context_mutates: Tuple[str, ...] = ()
    context_cache: Tuple[str, ...] = ()
    context_notes: str = "Role wrapper: injects role metadata and delegates propose/update to inner adapter."
    state_recovery_level: str = "L2"
    state_recovery_notes: str = "Transparently delegates population/token authority and inner adapter state restore."
    population_state_mode = "delegate"

    def __init__(
        self,
        role: str,
        inner: AlgorithmAdapter,
        *,
        name: Optional[str] = None,
        priority: int = 0,
        max_candidates: Optional[int] = None,
        context_requires: Sequence[str] = (),
        companions: Sequence[str] = (),
        recommended_suite: Optional[str] = None,
        strict_contract: bool = False,
    ) -> None:
        super().__init__(name=name or f"role:{role}", priority=priority)
        self.role = str(role)
        self.inner = inner
        if max_candidates is not None and int(max_candidates) < 0:
            raise ValueError("max_candidates must be non-negative")
        self.max_candidates = None if max_candidates is None else int(max_candidates)
        self.context_requires = tuple(str(k) for k in (context_requires or ()))
        self.companions = tuple(str(c) for c in (companions or ()))
        self.recommended_suite = recommended_suite
        self.strict_contract = bool(strict_contract)

        self._warned: set[str] = set()
        self.last_report: Dict[str, Any] = {}
        self._last_projection_writers: Dict[str, str] = {}

    def _warn_once(self, key: str, message: str) -> None:
        if key in self._warned:
            return
        warnings.warn(message, RuntimeWarning, stacklevel=3)
        self._warned.add(key)

    def _check_contract(self, context: Dict[str, Any]) -> None:
        missing = [k for k in self.context_requires if k not in context]
        if missing:
            msg = (
                f"RoleAdapter '{self.name}' (role='{self.role}') missing required context keys: {missing}. "
                "This role is controller-driven; provide these keys via ControllerAdapter/context/suite."
            )
            if self.strict_contract:
                raise KeyError(msg)
            self._warn_once(f"missing:{','.join(missing)}", msg)

        if self.companions:
            hint = (
                f"RoleAdapter '{self.name}' (role='{self.role}') has companions={list(self.companions)}"
                + (f", recommended_suite='{self.recommended_suite}'" if self.recommended_suite else "")
                + ". If behavior looks wrong, you may have forgotten to attach the companion components."
            )
            self._warn_once("companions", hint)

    def setup(self, control: Any) -> None:
        self._last_projection_writers = {}
        if self.inner is not None:
            self.inner.setup(control)

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self.inner is None:
            return []
        self._check_contract(context)
        ctx = dict(context)
        ctx[KEY_ROLE] = self.role
        ctx[KEY_ROLE_ADAPTER] = self.name
        proposed = self.coerce_candidates(self.inner.propose(control, ctx))
        proposed_count = len(proposed)
        if self.max_candidates is not None:
            proposed = proposed[: int(self.max_candidates)]
        if len(proposed) < proposed_count:
            self.inner.on_proposal_disposition(
                control,
                BatchDisposition.prefix(
                    proposed_count=proposed_count,
                    accepted_count=len(proposed),
                    reason="role_candidate_limit",
                    metadata={"role": self.role},
                ),
                ctx,
            )
        return proposed

    def on_proposal_disposition(
        self,
        control: Any,
        disposition: BatchDisposition,
        context: Dict[str, Any],
    ) -> None:
        if self.inner is None:
            raise RuntimeError(f"RoleAdapter '{self.name}' has no inner adapter")
        ctx = dict(context)
        ctx[KEY_ROLE] = self.role
        ctx[KEY_ROLE_ADAPTER] = self.name
        self.inner.on_proposal_disposition(control, disposition, ctx)

    def update(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        feedback: Any,
        context: Dict[str, Any],
    ) -> None:
        objectives, violations = feedback
        if self.inner is None:
            return
        self._check_contract(context)
        ctx = dict(context)
        ctx[KEY_ROLE] = self.role
        ctx[KEY_ROLE_ADAPTER] = self.name
        self.inner.update(control, candidates, feedback, ctx)
        self._update_report(control, candidates, objectives, violations, context)

    def teardown(self, control: Any) -> None:
        if self.inner is not None:
            self.inner.teardown(control)

    def _update_report(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> None:
        try:
            n = int(len(candidates) if candidates is not None else 0)
        except Exception:
            n = 0
        if n <= 0:
            self.last_report = {
                "role": self.role,
                "adapter": self.name,
                "n_candidates": 0,
                "best_idx": None,
                "best_objectives": None,
                "best_violation": None,
                "step": context.get(KEY_STEP),
            }
        else:
            obj = np.asarray(objectives) if objectives is not None else None
            vio = np.asarray(violations) if violations is not None else None

            if obj is None:
                best_idx = 0
            elif obj.ndim == 1:
                best_idx = int(np.argmin(obj))
            else:
                best_idx = int(np.argmin(np.sum(obj, axis=1)))

            best_x = None
            try:
                best_x = np.asarray(candidates[best_idx])
            except Exception:
                best_x = None

            best_obj = None
            if obj is not None:
                try:
                    best_obj = np.asarray(obj[best_idx]).copy()
                except Exception:
                    best_obj = None

            best_vio = None
            if vio is not None:
                try:
                    best_vio = float(vio[best_idx])
                except Exception:
                    best_vio = None

            self.last_report = {
                "role": self.role,
                "adapter": self.name,
                "n_candidates": n,
                "best_idx": best_idx,
                "best_x": best_x,
                "best_objectives": best_obj,
                "best_violation": best_vio,
                "step": context.get(KEY_STEP),
            }
        _ = control

    def get_state(self) -> Dict[str, Any]:
        inner = self.inner.get_state() if self.inner is not None else {}
        return {
            "schema": "nsgablack.role_adapter_state/v2",
            "role": self.role,
            "name": self.name,
            "max_candidates": self.max_candidates,
            "context_requires": list(self.context_requires),
            "companions": list(self.companions),
            "recommended_suite": self.recommended_suite,
            "strict_contract": self.strict_contract,
            "inner_name": None if self.inner is None else self.inner.name,
            "inner_class": (
                None
                if self.inner is None
                else f"{type(self.inner).__module__}.{type(self.inner).__qualname__}"
            ),
            "inner": inner,
            "population_partitions": [
                partition.as_dict()
                for partition in self.get_population_partitions()
            ],
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        schema = str(state.get("schema", "nsgablack.role_adapter_state/v1"))
        if schema not in {
            "nsgablack.role_adapter_state/v1",
            "nsgablack.role_adapter_state/v2",
        }:
            raise ValueError(f"unsupported RoleAdapter state schema: {schema}")
        saved_role = str(state.get("role", self.role))
        saved_name = str(state.get("name", self.name))
        if saved_role != self.role or saved_name != self.name:
            raise ValueError("RoleAdapter checkpoint identity mismatch")
        expected_config = {
            "max_candidates": self.max_candidates,
            "context_requires": tuple(self.context_requires),
            "companions": tuple(self.companions),
            "recommended_suite": self.recommended_suite,
            "strict_contract": self.strict_contract,
        }
        saved_config = {
            "max_candidates": state.get("max_candidates", self.max_candidates),
            "context_requires": tuple(
                str(item)
                for item in state.get("context_requires", self.context_requires)
            ),
            "companions": tuple(
                str(item) for item in state.get("companions", self.companions)
            ),
            "recommended_suite": state.get(
                "recommended_suite",
                self.recommended_suite,
            ),
            "strict_contract": bool(
                state.get("strict_contract", self.strict_contract)
            ),
        }
        if saved_config != expected_config:
            raise ValueError("RoleAdapter checkpoint configuration mismatch")
        if self.inner is not None:
            saved_inner_name = state.get("inner_name")
            saved_inner_class = state.get("inner_class")
            current_inner_class = (
                f"{type(self.inner).__module__}.{type(self.inner).__qualname__}"
            )
            if saved_inner_name is not None and str(saved_inner_name) != self.inner.name:
                raise ValueError("RoleAdapter inner adapter identity mismatch")
            if saved_inner_class is not None and str(saved_inner_class) != current_inner_class:
                raise ValueError("RoleAdapter inner adapter class mismatch")
        if self.inner is not None and isinstance(state.get("inner"), dict):
            self.inner.set_state(state["inner"])
        raw_partitions = tuple(state.get("population_partitions", ()) or ())
        if raw_partitions:
            self.set_population_partitions(
                tuple(PopulationPartition.from_dict(item) for item in raw_partitions)
            )

    def get_population_snapshot(
        self,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
        getter = getattr(self.inner, "get_population_snapshot", None)
        return getter() if callable(getter) else None

    def set_population_snapshot(
        self,
        population: np.ndarray,
        objectives: np.ndarray,
        violations: np.ndarray,
    ) -> bool:
        setter = getattr(self.inner, "set_population_snapshot", None)
        return (
            bool(setter(population, objectives, violations))
            if callable(setter)
            else False
        )

    def get_population_candidate_tokens(self) -> tuple[str | None, ...] | None:
        getter = getattr(self.inner, "get_population_candidate_tokens", None)
        return getter() if callable(getter) else None

    def set_population_candidate_tokens(
        self,
        candidate_tokens: Sequence[str | None],
    ) -> bool:
        setter = getattr(self.inner, "set_population_candidate_tokens", None)
        return bool(setter(candidate_tokens)) if callable(setter) else False

    def get_population_partitions(self) -> tuple[PopulationPartition, ...]:
        getter = getattr(self.inner, "get_population_partitions", None)
        return tuple(getter() or ()) if callable(getter) else ()

    def set_population_partitions(
        self,
        partitions: Sequence[PopulationPartition],
    ) -> bool:
        setter = getattr(self.inner, "set_population_partitions", None)
        return bool(setter(partitions)) if callable(setter) else False

    def get_context_contract(self) -> Dict[str, Any]:
        contract = super().get_context_contract()
        notes = list()
        base_notes = contract.get("notes")
        if base_notes:
            notes.append(str(base_notes))
        if self.companions:
            notes.append("companions=" + ", ".join(str(x) for x in self.companions))
        if self.recommended_suite:
            notes.append(f"recommended_suite={self.recommended_suite}")
        return {
            **contract,
            "notes": " | ".join(notes) if notes else None,
        }

    def get_runtime_context_projection(self, solver: Any) -> RuntimeContextProjection:
        children = ()
        if self.inner is not None:
            children = (
                (
                    f"adapter.role.{self.role}.inner:{self.inner.__class__.__name__}",
                    self.inner,
                ),
            )
        aggregation = aggregate_adapter_runtime_projections(
            solver,
            owner_source=f"adapter.{self.__class__.__name__}",
            children=children,
        )
        self._last_projection_writers = dict(aggregation.field_sources)
        return aggregation.projection

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        del solver
        return dict(self._last_projection_writers)


class RoleRouterAdapter(AlgorithmAdapter):
    """Orchestrate multiple RoleAdapter instances.

    This adapter:
    - Calls each role adapter to produce candidates
    - Records candidate -> role mapping for later analysis/plugins
    - Dispatches evaluation feedback back to each role adapter
    """

    context_contract_encapsulates_children = True

    def __init__(
        self,
        roles: Sequence[RoleAdapter],
        *,
        name: str = "multi_role_controller",
        priority: int = 0,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.roles = list(roles)
        role_names = [str(role.name) for role in self.roles]
        if len(role_names) != len(set(role_names)):
            raise ValueError("RoleRouterAdapter role adapter names must be unique")
        self._last_ranges: List[Tuple[RoleAdapter, int, int]] = []
        self.last_candidate_roles: List[str] = []
        self._runtime_projection: Dict[str, Any] = {}
        self._last_projection_writers: Dict[str, str] = {}

    context_requires = ("generation",)
    context_provides = (KEY_ROLE, KEY_ROLE_INDEX, KEY_ROLE_REPORTS, KEY_CANDIDATE_ROLES)
    context_mutates = (KEY_ROLE_REPORTS, KEY_CANDIDATE_ROLES)
    context_cache = ()
    context_notes = "Controller for RoleAdapter set: dispatches candidates and returns role-scoped feedback."
    state_recovery_level = "L2"
    state_recovery_notes = "Restores stable role population partitions, tokens, and role adapter states."
    population_state_mode = "partitioned"

    def setup(self, control: Any) -> None:
        self._runtime_projection = {}
        self._last_projection_writers = {}
        for role in self.roles:
            role.setup(control)

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        candidates: List[np.ndarray] = []
        self._last_ranges = []
        self.last_candidate_roles = []

        for idx, role in enumerate(self.roles):
            start = len(candidates)
            ctx = dict(context)
            ctx[KEY_ROLE] = role.role
            ctx[KEY_ROLE_INDEX] = idx
            proposed = self.coerce_candidates(role.propose(control, ctx))
            candidates.extend(proposed)
            end = len(candidates)
            self._last_ranges.append((role, start, end))
            self.last_candidate_roles.extend([role.role] * (end - start))

        self._runtime_projection[KEY_CANDIDATE_ROLES] = list(self.last_candidate_roles)
        self._runtime_projection[KEY_ROLE_REPORTS] = self._collect_role_reports()
        return candidates

    def on_proposal_disposition(
        self,
        control: Any,
        disposition: BatchDisposition,
        context: Dict[str, Any],
    ) -> None:
        reconciled: List[Tuple[RoleAdapter, int, int]] = []
        candidate_roles: List[str] = []
        cursor = 0
        for idx, (role, start, end) in enumerate(self._last_ranges):
            child = disposition.for_range(start, end)
            ctx = dict(context)
            ctx[KEY_ROLE] = role.role
            ctx[KEY_ROLE_INDEX] = idx
            role.on_proposal_disposition(control, child, ctx)
            if child.accepted_count == 0:
                continue
            next_cursor = cursor + child.accepted_count
            reconciled.append((role, cursor, next_cursor))
            candidate_roles.extend([role.role] * child.accepted_count)
            cursor = next_cursor
        self._last_ranges = reconciled
        self.last_candidate_roles = candidate_roles
        self._runtime_projection[KEY_CANDIDATE_ROLES] = list(candidate_roles)

    def update(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        feedback: Any,
        context: Dict[str, Any],
    ) -> None:
        objectives, violations = feedback
        if not self._last_ranges:
            if len(candidates) == 0:
                return
            raise RuntimeError("RoleRouterAdapter.update requires a preceding propose call")
        expected_count = sum(end - start for _role, start, end in self._last_ranges)
        if len(candidates) != expected_count:
            raise ValueError(
                "role-router feedback does not match role proposal ranges: "
                f"candidates={len(candidates)}, allocated={expected_count}"
            )
        if len(objectives) != expected_count or len(violations) != expected_count:
            raise ValueError("role-router candidate, objective, and violation counts must match")

        for idx, (role, start, end) in enumerate(self._last_ranges):
            if start == end:
                continue
            ctx = dict(context)
            ctx[KEY_ROLE] = role.role
            ctx[KEY_ROLE_INDEX] = idx
            role.update(
                control,
                candidates[start:end],
                subset_adapter_feedback(feedback, slice(start, end)),
                ctx,
            )
        self._runtime_projection[KEY_CANDIDATE_ROLES] = list(self.last_candidate_roles)
        self._runtime_projection[KEY_ROLE_REPORTS] = self._collect_role_reports()

    def teardown(self, control: Any) -> None:
        for role in self.roles:
            role.teardown(control)

    def get_state(self) -> Dict[str, Any]:
        return {
            "schema": "nsgablack.role_router_state/v2",
            "role_order": [r.name for r in self.roles],
            "roles": {r.name: r.get_state() for r in self.roles},
            "population_partitions": [
                partition.as_dict()
                for partition in self.get_population_partitions()
            ],
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        schema = str(state.get("schema", "nsgablack.role_router_state/v1"))
        if schema not in {
            "nsgablack.role_router_state/v1",
            "nsgablack.role_router_state/v2",
        }:
            raise ValueError(f"unsupported RoleRouterAdapter state schema: {schema}")
        saved_order = tuple(str(item) for item in state.get("role_order", ()))
        current_order = tuple(str(role.name) for role in self.roles)
        if saved_order and saved_order != current_order:
            raise ValueError("RoleRouterAdapter role identity mismatch")
        roles = state.get("roles")
        if not isinstance(roles, dict):
            raise ValueError("RoleRouterAdapter checkpoint is missing role states")
        if set(roles) != set(current_order):
            raise ValueError("RoleRouterAdapter role state set mismatch")
        for r in self.roles:
            if r.name in roles and isinstance(roles[r.name], dict):
                r.set_state(roles[r.name])
        raw_partitions = tuple(state.get("population_partitions", ()) or ())
        if raw_partitions:
            self.set_population_partitions(
                tuple(PopulationPartition.from_dict(item) for item in raw_partitions)
            )

    def _role_prefix(self, index: int, role: RoleAdapter) -> str:
        return f"role:{int(index)}:{role.role}:{role.name}"

    def get_population_partitions(self) -> tuple[PopulationPartition, ...]:
        out: list[PopulationPartition] = []
        for index, role in enumerate(self.roles):
            out.extend(
                prefixed_population_partitions(
                    self._role_prefix(index, role),
                    role,
                )
            )
        return tuple(out)

    def set_population_partitions(
        self,
        partitions: Sequence[PopulationPartition],
    ) -> bool:
        values = tuple(partitions or ())
        handled = False
        for index, role in enumerate(self.roles):
            handled = (
                restore_prefixed_population_partitions(
                    self._role_prefix(index, role),
                    role,
                    values,
                )
                or handled
            )
        known_prefixes = tuple(
            self._role_prefix(index, role) + "/"
            for index, role in enumerate(self.roles)
        )
        unknown = tuple(
            partition.partition_id
            for partition in values
            if not partition.partition_id.startswith(known_prefixes)
        )
        if unknown:
            raise ValueError(
                "RoleRouterAdapter checkpoint contains unknown population partitions: "
                + ", ".join(sorted(unknown))
            )
        return handled or not values

    def _collect_role_reports(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for role in self.roles:
            report = getattr(role, "last_report", None)
            if isinstance(report, dict) and report:
                out[str(role.role)] = dict(report)
        return out

    def get_runtime_context_projection(self, solver: Any) -> RuntimeContextProjection:
        aggregation = aggregate_adapter_runtime_projections(
            solver,
            owner_source=f"adapter.{self.__class__.__name__}",
            own_fields=self._runtime_projection,
            children=tuple(
                (
                    f"adapter.role.{role.role}:{role.__class__.__name__}",
                    role,
                )
                for role in self.roles
            ),
        )
        self._last_projection_writers = dict(aggregation.field_sources)
        return aggregation.projection

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        del solver
        return dict(self._last_projection_writers)


class MultiRoleControllerAdapter(RoleRouterAdapter):
    context_requires = RoleRouterAdapter.context_requires
    context_provides = RoleRouterAdapter.context_provides
    context_mutates = RoleRouterAdapter.context_mutates
    context_cache = RoleRouterAdapter.context_cache
    context_notes = RoleRouterAdapter.context_notes
