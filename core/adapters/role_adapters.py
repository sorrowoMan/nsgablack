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

from .algorithm_adapter import AlgorithmAdapter
from ...utils.context.context_keys import KEY_ROLE, KEY_ROLE_ADAPTER, KEY_ROLE_INDEX, KEY_ROLE_REPORTS


@dataclass
class RoleAdapter(AlgorithmAdapter):
    """Wrap an adapter with role metadata and optional candidate limiting."""

    role: str = "role"
    inner: Optional[AlgorithmAdapter] = None
    max_candidates: Optional[int] = None
    requires_context_keys: Tuple[str, ...] = ()
    companions: Tuple[str, ...] = ()
    recommended_suite: Optional[str] = None
    strict_contract: bool = False

    def __init__(
        self,
        role: str,
        inner: AlgorithmAdapter,
        *,
        name: Optional[str] = None,
        priority: int = 0,
        max_candidates: Optional[int] = None,
        requires_context_keys: Sequence[str] = (),
        companions: Sequence[str] = (),
        recommended_suite: Optional[str] = None,
        strict_contract: bool = False,
    ) -> None:
        super().__init__(name=name or f"role:{role}", priority=priority)
        self.role = str(role)
        self.inner = inner
        self.max_candidates = max_candidates
        self.requires_context_keys = tuple(str(k) for k in (requires_context_keys or ()))
        self.companions = tuple(str(c) for c in (companions or ()))
        self.recommended_suite = recommended_suite
        self.strict_contract = bool(strict_contract)

        self._warned: set[str] = set()
        self.last_report: Dict[str, Any] = {}

    def _warn_once(self, key: str, message: str) -> None:
        if key in self._warned:
            return
        warnings.warn(message, RuntimeWarning, stacklevel=3)
        self._warned.add(key)

    def _check_contract(self, context: Dict[str, Any]) -> None:
        missing = [k for k in self.requires_context_keys if k not in context]
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

    def setup(self, solver: Any) -> None:
        if self.inner is not None:
            self.inner.setup(solver)

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self.inner is None:
            return []
        self._check_contract(context)
        ctx = dict(context)
        ctx[KEY_ROLE] = self.role
        ctx[KEY_ROLE_ADAPTER] = self.name
        proposed = list(self.inner.propose(solver, ctx) or [])
        if self.max_candidates is not None:
            proposed = proposed[: int(self.max_candidates)]
        return proposed

    def update(
        self,
        solver: Any,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> None:
        if self.inner is None:
            return
        self._check_contract(context)
        ctx = dict(context)
        ctx[KEY_ROLE] = self.role
        ctx[KEY_ROLE_ADAPTER] = self.name
        self.inner.update(solver, candidates, objectives, violations, ctx)
        self._update_report(solver, candidates, objectives, violations, context)

    def teardown(self, solver: Any) -> None:
        if self.inner is not None:
            self.inner.teardown(solver)

    def _update_report(
        self,
        solver: Any,
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
                "step": context.get("step"),
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
                "step": context.get("step"),
            }

        # Best-effort: expose on solver for controller/plugins.
        try:
            reports = getattr(solver, "role_reports", None)
            if not isinstance(reports, dict):
                reports = {}
                setattr(solver, "role_reports", reports)
            reports[self.role] = dict(self.last_report)
        except Exception:
            pass

        # Also mirror into solver.shared_state when available.
        try:
            shared = getattr(solver, "shared_state", None)
            if isinstance(shared, dict):
                shared.setdefault(KEY_ROLE_REPORTS, {})
                if isinstance(shared.get(KEY_ROLE_REPORTS), dict):
                    shared[KEY_ROLE_REPORTS][self.role] = dict(self.last_report)
        except Exception:
            pass

    def get_state(self) -> Dict[str, Any]:
        inner = self.inner.get_state() if self.inner is not None else {}
        return {
            "role": self.role,
            "name": self.name,
            "max_candidates": self.max_candidates,
            "requires_context_keys": list(self.requires_context_keys),
            "companions": list(self.companions),
            "recommended_suite": self.recommended_suite,
            "strict_contract": self.strict_contract,
            "inner": inner,
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        if "role" in state:
            self.role = str(state["role"])
        if "max_candidates" in state:
            self.max_candidates = state["max_candidates"]
        if "requires_context_keys" in state and isinstance(state["requires_context_keys"], (list, tuple)):
            self.requires_context_keys = tuple(str(k) for k in state["requires_context_keys"])
        if "companions" in state and isinstance(state["companions"], (list, tuple)):
            self.companions = tuple(str(c) for c in state["companions"])
        if "recommended_suite" in state:
            self.recommended_suite = state["recommended_suite"]
        if "strict_contract" in state:
            self.strict_contract = bool(state["strict_contract"])
        if self.inner is not None and isinstance(state.get("inner"), dict):
            self.inner.set_state(state["inner"])


class MultiRoleControllerAdapter(AlgorithmAdapter):
    """Orchestrate multiple RoleAdapter instances.

    This adapter:
    - Calls each role adapter to produce candidates
    - Records candidate -> role mapping for later analysis/plugins
    - Dispatches evaluation feedback back to each role adapter
    """

    def __init__(
        self,
        roles: Sequence[RoleAdapter],
        *,
        name: str = "multi_role_controller",
        priority: int = 0,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.roles = list(roles)
        self._last_ranges: List[Tuple[RoleAdapter, int, int]] = []
        self.last_candidate_roles: List[str] = []

    def setup(self, solver: Any) -> None:
        for role in self.roles:
            role.setup(solver)

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        candidates: List[np.ndarray] = []
        self._last_ranges = []
        self.last_candidate_roles = []

        for idx, role in enumerate(self.roles):
            start = len(candidates)
            ctx = dict(context)
            ctx[KEY_ROLE] = role.role
            ctx[KEY_ROLE_INDEX] = idx
            proposed = list(role.propose(solver, ctx) or [])
            candidates.extend(proposed)
            end = len(candidates)
            self._last_ranges.append((role, start, end))
            self.last_candidate_roles.extend([role.role] * (end - start))

        # Expose mapping on solver for optional plugins/analysis.
        try:
            solver.last_candidate_roles = list(self.last_candidate_roles)
        except Exception:
            pass

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
            # Fallback: dispatch full batch to all roles.
            for role in self.roles:
                role.update(solver, candidates, objectives, violations, context)
            return

        for idx, (role, start, end) in enumerate(self._last_ranges):
            if start == end:
                continue
            ctx = dict(context)
            ctx[KEY_ROLE] = role.role
            ctx[KEY_ROLE_INDEX] = idx
            role.update(
                solver,
                candidates[start:end],
                objectives[start:end],
                violations[start:end],
                ctx,
            )

    def teardown(self, solver: Any) -> None:
        for role in self.roles:
            role.teardown(solver)

    def get_state(self) -> Dict[str, Any]:
        return {
            "roles": {r.name: r.get_state() for r in self.roles},
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        roles = state.get("roles")
        if not isinstance(roles, dict):
            return
        for r in self.roles:
            if r.name in roles and isinstance(roles[r.name], dict):
                r.set_state(roles[r.name])
