"""Controller control-plane primitives for L3 runtime governance."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from blackbase.plugin import (
    ATTEMPT_START,
    GENERATION_END,
    normalize_lifecycle_slot,
)


class ControlConflictError(RuntimeError):
    """Raised when decisions conflict under strict policy."""


class ControllerDispatchError(RuntimeError):
    """One or more Controllers failed after every slot participant ran."""

    def __init__(
        self,
        *,
        slot: str,
        errors: Sequence[tuple[str, BaseException]],
    ) -> None:
        self.slot = str(slot)
        self.errors = tuple(errors)
        summary = "; ".join(
            f"{name}: {type(exc).__name__}: {exc}"
            for name, exc in self.errors
        )
        super().__init__(f"controller slot '{self.slot}' failed: {summary}")


class EvaluationBudgetExceeded(RuntimeError):
    """Raised before evaluation when a request would exceed the hard budget."""


@dataclass(frozen=True)
class ControlDecision:
    domain: str
    slot: str
    controller: str
    target_scope: str = "global"
    priority: int = 0
    payload: Mapping[str, Any] | None = None
    reason: str = ""


class BaseController(ABC):
    """Abstract controller for L3 runtime control decisions."""

    domain: str = "generic"
    slots: Tuple[str, ...] = (GENERATION_END,)
    owns_domains: Tuple[str, ...] = ()

    def __init__(self, *, name: str, priority: int = 0, enabled: bool = True) -> None:
        self.name = str(name)
        self.priority = int(priority)
        self.enabled = bool(enabled)
        if not self.owns_domains:
            self.owns_domains = (str(self.domain),)

    @abstractmethod
    def propose(self, solver: Any, slot: str, context: Mapping[str, Any]) -> Optional[ControlDecision]:
        raise NotImplementedError

    def checkpoint_identity(self) -> Mapping[str, Any]:
        return {
            "name": self.name,
            "module": type(self).__module__,
            "class": type(self).__qualname__,
            "domain": self.domain,
            "slots": list(self.slots),
            "priority": self.priority,
        }

    def get_state(self) -> Mapping[str, Any]:
        return {
            "schema": "nsgablack.controller_state/v1",
            "name": self.name,
            "enabled": self.enabled,
        }

    def set_state(self, state: Mapping[str, Any]) -> None:
        data = dict(state or {})
        if str(data.get("schema", "")) != "nsgablack.controller_state/v1":
            raise ValueError("unsupported controller state schema")
        if str(data.get("name", "")) != self.name:
            raise ValueError("controller state name mismatch")
        self.enabled = bool(data.get("enabled", self.enabled))


class ControlArbiter:
    """Resolve multiple control decisions into one per domain."""

    def __init__(self, *, strict: bool = True) -> None:
        self.strict = bool(strict)

    def resolve(self, decisions: Sequence[ControlDecision]) -> Dict[str, ControlDecision]:
        by_domain: Dict[str, List[ControlDecision]] = {}
        for d in decisions:
            by_domain.setdefault(str(d.domain), []).append(d)

        out: Dict[str, ControlDecision] = {}
        for domain, rows in by_domain.items():
            rows_sorted = sorted(rows, key=lambda x: (int(x.priority), str(x.controller)))
            if domain == "stopping":
                stop = False
                reason_parts: List[str] = []
                for row in rows_sorted:
                    payload = dict(row.payload or {})
                    if bool(payload.get("stop", False)):
                        stop = True
                        if row.reason:
                            reason_parts.append(str(row.reason))
                out[domain] = ControlDecision(
                    domain=domain,
                    slot=rows_sorted[0].slot,
                    controller="arbiter",
                    priority=rows_sorted[0].priority,
                    payload={"stop": stop},
                    reason="; ".join(reason_parts),
                )
                continue

            if len(rows_sorted) == 1:
                out[domain] = rows_sorted[0]
                continue

            # Budget can be merged conservatively by min if key exists.
            if domain == "budget":
                mins: Dict[str, float] = {}
                slot = rows_sorted[0].slot
                for row in rows_sorted:
                    payload = dict(row.payload or {})
                    for k, v in payload.items():
                        try:
                            fv = float(v)
                        except Exception:
                            continue
                        mins[k] = fv if k not in mins else min(mins[k], fv)
                if mins:
                    out[domain] = ControlDecision(
                        domain=domain,
                        slot=slot,
                        controller="arbiter",
                        payload=mins,
                        priority=min(r.priority for r in rows_sorted),
                        reason="budget-min-merge",
                    )
                    continue

            if self.strict:
                names = ", ".join(f"{r.controller}@p{r.priority}" for r in rows_sorted)
                raise ControlConflictError(f"domain '{domain}' has multiple decisions: {names}")
            out[domain] = rows_sorted[0]
        return out


class RuntimeController:
    """Collect decisions by slot and resolve them with arbiter."""

    def __init__(self, *, arbiter: Optional[ControlArbiter] = None) -> None:
        self._controllers: List[BaseController] = []
        self._arbiter = arbiter or ControlArbiter(strict=True)

    def register_controller(self, controller: BaseController) -> None:
        if any(c.name == controller.name for c in self._controllers):
            raise ValueError(f"Controller '{controller.name}' already registered")
        controller.slots = tuple(
            normalize_lifecycle_slot(slot)
            for slot in tuple(getattr(controller, "slots", ()) or ())
        )
        for owner_domain in tuple(getattr(controller, "owns_domains", ()) or ()):
            owner_domain_text = str(owner_domain).strip()
            if not owner_domain_text:
                continue
            for existing in self._controllers:
                existing_domains = tuple(getattr(existing, "owns_domains", ()) or ())
                if owner_domain_text in {str(x).strip() for x in existing_domains}:
                    raise ValueError(
                        f"Domain '{owner_domain_text}' already owned by controller '{existing.name}'"
                    )
        self._controllers.append(controller)

    def list_controllers(self) -> Tuple[BaseController, ...]:
        return tuple(self._controllers)

    def collect(self, solver: Any, *, slot: str, context: Mapping[str, Any]) -> Tuple[ControlDecision, ...]:
        slot = normalize_lifecycle_slot(slot)
        out: List[ControlDecision] = []
        errors: List[tuple[str, BaseException]] = []
        for c in sorted(self._controllers, key=lambda x: (int(x.priority), str(x.name))):
            if not bool(c.enabled):
                continue
            if slot not in set(str(s) for s in c.slots):
                continue
            try:
                d = c.propose(solver, slot, context)
            except BaseException as exc:
                errors.append((str(c.name), exc))
                continue
            if d is None:
                continue
            out.append(d)
        if errors:
            raise ControllerDispatchError(slot=slot, errors=errors) from errors[0][1]
        return tuple(out)

    def resolve(self, solver: Any, *, slot: str, context: Mapping[str, Any]) -> Dict[str, ControlDecision]:
        decisions = self.collect(solver, slot=slot, context=context)
        return self._arbiter.resolve(decisions)

    def validate_configuration(self) -> None:
        owners: Dict[str, str] = {}
        for controller in self._controllers:
            for owner_domain in tuple(getattr(controller, "owns_domains", ()) or ()):
                owner_domain_text = str(owner_domain).strip()
                if not owner_domain_text:
                    continue
                existing = owners.get(owner_domain_text)
                if existing is not None and existing != controller.name:
                    raise ValueError(
                        f"Domain '{owner_domain_text}' has multiple owners: {existing}, {controller.name}"
                    )
                owners[owner_domain_text] = controller.name

    def checkpoint_identity(self) -> Mapping[str, Any]:
        return {
            "schema": "nsgablack.runtime_controller_identity/v1",
            "controllers": [
                dict(controller.checkpoint_identity())
                for controller in sorted(
                    self._controllers,
                    key=lambda item: str(item.name),
                )
            ],
        }

    def get_state(self) -> Mapping[str, Any]:
        return {
            "schema": "nsgablack.runtime_controller_state/v1",
            "controllers": {
                controller.name: {
                    "module": type(controller).__module__,
                    "class": type(controller).__qualname__,
                    "state": dict(controller.get_state()),
                }
                for controller in self._controllers
            },
        }

    def set_state(self, state: Mapping[str, Any]) -> None:
        data = dict(state or {})
        if str(data.get("schema", "")) != "nsgablack.runtime_controller_state/v1":
            raise ValueError("unsupported RuntimeController state schema")
        saved = dict(data.get("controllers", {}) or {})
        current = {controller.name: controller for controller in self._controllers}
        if set(saved) != set(current):
            raise ValueError(
                "RuntimeController checkpoint names do not match the configured controllers"
            )
        for name, controller in current.items():
            payload = saved[name]
            if not isinstance(payload, Mapping):
                raise ValueError(f"invalid controller checkpoint payload: {name}")
            if (
                str(payload.get("module", "")) != type(controller).__module__
                or str(payload.get("class", "")) != type(controller).__qualname__
            ):
                raise ValueError(f"controller checkpoint type mismatch: {name}")
            controller.set_state(dict(payload.get("state", {}) or {}))

    def evaluation_allowance(
        self,
        solver: Any,
        *,
        requested: int,
        context: Optional[Mapping[str, Any]] = None,
    ) -> int:
        """Return the maximum safe batch size under every active controller."""
        allowed = max(0, int(requested))
        ctx = dict(context or {})
        for controller in sorted(
            self._controllers,
            key=lambda item: (int(item.priority), str(item.name)),
        ):
            if not bool(controller.enabled):
                continue
            limiter = getattr(controller, "evaluation_allowance", None)
            if not callable(limiter):
                continue
            candidate = limiter(solver, requested=allowed, context=ctx)
            if candidate is None:
                continue
            allowed = min(allowed, max(0, int(candidate)))
        return allowed


class BudgetController(BaseController):
    """Concrete controller for budget-domain decisions (max generations, evaluations)."""

    domain = "budget"
    slots: Tuple[str, ...] = (ATTEMPT_START, GENERATION_END)
    owns_domains: Tuple[str, ...] = ("budget",)

    def __init__(self, *, max_generations: int | None = None, max_evaluations: int | None = None, name: str = "budget", priority: int = 0) -> None:
        super().__init__(name=name, priority=priority)
        self.max_generations = max_generations
        self.max_evaluations = max_evaluations

    def evaluation_allowance(
        self,
        solver: Any,
        *,
        requested: int,
        context: Mapping[str, Any],
    ) -> int:
        """Cap one atomic evaluation batch without letting it cross the limit."""
        if self.max_evaluations is None:
            return max(0, int(requested))
        evaluations = int(
            context.get(
                "evaluation_count",
                context.get(
                    "total_evaluations",
                    getattr(solver, "evaluation_count", 0),
                ),
            )
            or 0
        )
        remaining = max(0, int(self.max_evaluations) - evaluations)
        return min(max(0, int(requested)), remaining)

    def propose(self, solver: Any, slot: str, context: Mapping[str, Any]) -> Optional[ControlDecision]:
        payload: Dict[str, float] = {}
        if self.max_generations is not None and str(slot) == GENERATION_END:
            gen = int(context.get("generation", 0))
            if gen + 1 >= self.max_generations:
                payload["stop"] = 1.0
        if self.max_evaluations is not None:
            evals = int(context.get("evaluation_count", context.get("total_evaluations", 0)))
            payload["max_evaluations"] = float(self.max_evaluations)
            payload["remaining_evaluations"] = float(
                max(0, int(self.max_evaluations) - evals)
            )
            if evals >= self.max_evaluations:
                payload["stop"] = 1.0
        if not payload:
            return None
        reason = "budget exhausted" if bool(payload.get("stop", False)) else "budget active"
        return ControlDecision(
            domain="budget",
            slot=slot,
            controller=self.name,
            payload=payload,
            reason=reason,
        )

    def checkpoint_identity(self) -> Mapping[str, Any]:
        return {
            **dict(super().checkpoint_identity()),
            "max_generations": self.max_generations,
            "max_evaluations": self.max_evaluations,
        }


class StopController(BaseController):
    """Concrete controller for stopping-domain decisions."""

    domain = "stopping"
    slots: Tuple[str, ...] = (GENERATION_END,)
    owns_domains: Tuple[str, ...] = ("stopping",)

    def __init__(self, *, patience: int | None = None, min_delta: float = 1e-8, name: str = "stop", priority: int = 0) -> None:
        super().__init__(name=name, priority=priority)
        self.patience = patience
        self.min_delta = min_delta
        self._best: float | None = None
        self._stale: int = 0

    def propose(self, solver: Any, slot: str, context: Mapping[str, Any]) -> Optional[ControlDecision]:
        best_obj = context.get("best_objective")
        if best_obj is None:
            return None
        try:
            current = float(best_obj)
        except (TypeError, ValueError):
            return None
        if self._best is None or current < self._best - self.min_delta:
            self._best = current
            self._stale = 0
        else:
            self._stale += 1
        if self.patience is not None and self._stale >= self.patience:
            return ControlDecision(domain="stopping", slot=slot, controller=self.name, payload={"stop": True}, reason="patience exhausted")
        return None

    def checkpoint_identity(self) -> Mapping[str, Any]:
        return {
            **dict(super().checkpoint_identity()),
            "patience": self.patience,
            "min_delta": self.min_delta,
        }

    def get_state(self) -> Mapping[str, Any]:
        return {
            **dict(super().get_state()),
            "best": self._best,
            "stale": self._stale,
        }

    def set_state(self, state: Mapping[str, Any]) -> None:
        super().set_state(state)
        data = dict(state or {})
        raw_best = data.get("best")
        self._best = None if raw_best is None else float(raw_best)
        self._stale = max(0, int(data.get("stale", 0) or 0))
