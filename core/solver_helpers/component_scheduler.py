"""Dependency-aware component execution scheduler for solver control plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Set


class ComponentOrderError(ValueError):
    """Raised when component execution order cannot be resolved."""


@dataclass
class _ComponentRecord:
    name: str
    priority: int
    registration_index: int


def _norm_names(values: Optional[Iterable[str]]) -> Set[str]:
    out: Set[str] = set()
    if values is None:
        return out
    for value in values:
        text = str(value).strip()
        if text:
            out.add(text)
    return out


class ComponentDependencyScheduler:
    """Resolves a deterministic component order with dependency constraints.

    Ordering policy:
    1) Hard constraints (`depends_on`, `after`, `before`) are respected first.
    2) Among currently eligible nodes, smaller `priority` runs earlier.
    3) Ties are broken by registration order (stable), then name.
    """

    def __init__(self) -> None:
        self._records: Dict[str, _ComponentRecord] = {}
        self._rules: Dict[str, Dict[str, Set[str]]] = {}
        self._counter: int = 0

    def register_component(self, name: str, *, priority: int = 0) -> None:
        key = str(name).strip()
        if not key:
            raise ComponentOrderError("component name cannot be empty")
        rec = self._records.get(key)
        if rec is None:
            self._records[key] = _ComponentRecord(
                name=key,
                priority=int(priority),
                registration_index=int(self._counter),
            )
            self._counter += 1
        else:
            rec.priority = int(priority)
        self._rules.setdefault(
            key,
            {"depends_on": set(), "before": set(), "after": set()},
        )

    def unregister_component(self, name: str) -> None:
        key = str(name).strip()
        if not key:
            return
        self._records.pop(key, None)
        self._rules.pop(key, None)
        for rule in self._rules.values():
            rule["depends_on"].discard(key)
            rule["before"].discard(key)
            rule["after"].discard(key)

    def snapshot_rules(self) -> Dict[str, Dict[str, Set[str]]]:
        return {
            name: {
                "depends_on": set(rule.get("depends_on", set())),
                "before": set(rule.get("before", set())),
                "after": set(rule.get("after", set())),
            }
            for name, rule in self._rules.items()
        }

    def restore_rules(self, rules: Mapping[str, Mapping[str, Iterable[str]]]) -> None:
        restored: Dict[str, Dict[str, Set[str]]] = {}
        for name in self._records.keys():
            src = rules.get(name, {})
            restored[name] = {
                "depends_on": _norm_names(src.get("depends_on")),
                "before": _norm_names(src.get("before")),
                "after": _norm_names(src.get("after")),
            }
        self._rules = restored

    def set_constraints(
        self,
        name: str,
        *,
        depends_on: Optional[Iterable[str]] = None,
        before: Optional[Iterable[str]] = None,
        after: Optional[Iterable[str]] = None,
    ) -> None:
        key = str(name).strip()
        if key not in self._records:
            raise ComponentOrderError(f"component not registered: {key}")
        candidate = self.validate_constraints(
            key,
            depends_on=depends_on,
            before=before,
            after=after,
        )
        self._rules[key] = candidate

    def validate_constraints(
        self,
        name: str,
        *,
        depends_on: Optional[Iterable[str]] = None,
        before: Optional[Iterable[str]] = None,
        after: Optional[Iterable[str]] = None,
    ) -> Dict[str, Set[str]]:
        key = str(name).strip()
        if key not in self._records:
            raise ComponentOrderError(f"component not registered: {key}")
        current = self._rules.setdefault(
            key,
            {"depends_on": set(), "before": set(), "after": set()},
        )
        candidate = {
            "depends_on": set(current.get("depends_on", set())),
            "before": set(current.get("before", set())),
            "after": set(current.get("after", set())),
        }
        if depends_on is not None:
            candidate["depends_on"] = _norm_names(depends_on)
        if before is not None:
            candidate["before"] = _norm_names(before)
        if after is not None:
            candidate["after"] = _norm_names(after)

        self._validate_single_rule(key, candidate)
        rules_copy = self.snapshot_rules()
        rules_copy[key] = {
            "depends_on": set(candidate["depends_on"]),
            "before": set(candidate["before"]),
            "after": set(candidate["after"]),
        }
        # Validate global consistency with this candidate applied.
        self._resolve_order_internal(records=self._records, rules=rules_copy, strict=True)
        return candidate

    def resolve_order(self) -> List[str]:
        return self.resolve_order_strict()

    def resolve_order_strict(self) -> List[str]:
        return self._resolve_order_internal(records=self._records, rules=self._rules, strict=True)

    def _resolve_order_internal(
        self,
        *,
        records: Mapping[str, _ComponentRecord],
        rules: Mapping[str, Mapping[str, Set[str]]],
        strict: bool,
    ) -> List[str]:
        nodes = list(records.keys())
        prereq: Dict[str, Set[str]] = {name: set() for name in nodes}
        succ: Dict[str, Set[str]] = {name: set() for name in nodes}

        for name in nodes:
            rule = rules.get(name, {})
            dep = _norm_names(rule.get("depends_on"))
            aft = _norm_names(rule.get("after"))
            bef = _norm_names(rule.get("before"))
            if strict:
                self._validate_single_rule(
                    name,
                    {"depends_on": dep, "before": bef, "after": aft},
                    records=records,
                )

            for pred in dep | aft:
                if pred in prereq:
                    prereq[name].add(pred)
            for target in bef:
                if target in prereq:
                    prereq[target].add(name)

        for name in nodes:
            for pred in prereq[name]:
                succ[pred].add(name)

        indeg: Dict[str, int] = {name: len(preds) for name, preds in prereq.items()}
        ready: List[str] = [name for name in nodes if indeg[name] == 0]
        order: List[str] = []

        while ready:
            ready.sort(key=self._sort_key)
            name = ready.pop(0)
            order.append(name)
            for nxt in list(succ[name]):
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    ready.append(nxt)

        if len(order) != len(nodes):
            unresolved = sorted([name for name in nodes if name not in set(order)])
            edge_hints: List[str] = []
            for dst in unresolved:
                for src in sorted(prereq.get(dst, set())):
                    if src in unresolved:
                        edge_hints.append(f"{src}->{dst}")
                    if len(edge_hints) >= 10:
                        break
                if len(edge_hints) >= 10:
                    break
            detail = ""
            if edge_hints:
                detail = " | edges: " + ", ".join(edge_hints)
            raise ComponentOrderError(
                "component dependency cycle detected: "
                + ", ".join(unresolved)
                + detail
            )
        return order

    def _sort_key(self, name: str):
        rec = self._records[name]
        return (int(rec.priority), int(rec.registration_index), str(rec.name))

    def _validate_single_rule(
        self,
        name: str,
        rule: Mapping[str, Set[str]],
        *,
        records: Optional[Mapping[str, _ComponentRecord]] = None,
    ) -> None:
        recs = self._records if records is None else records
        if name not in recs:
            raise ComponentOrderError(f"component not registered: {name}")
        dep = _norm_names(rule.get("depends_on"))
        aft = _norm_names(rule.get("after"))
        bef = _norm_names(rule.get("before"))
        if name in dep:
            raise ComponentOrderError(f"component '{name}' cannot depend on itself")
        if name in aft:
            raise ComponentOrderError(f"component '{name}' cannot be after itself")
        if name in bef:
            raise ComponentOrderError(f"component '{name}' cannot be before itself")

        unknown = sorted([x for x in (dep | aft | bef) if x not in recs])
        if unknown:
            raise ComponentOrderError(
                f"component '{name}' references unknown component(s): {', '.join(unknown)}"
            )

        overlap_before_after = sorted(bef & aft)
        if overlap_before_after:
            raise ComponentOrderError(
                f"component '{name}' has contradictory before/after for: "
                + ", ".join(overlap_before_after)
            )
        overlap_before_dep = sorted(bef & dep)
        if overlap_before_dep:
            raise ComponentOrderError(
                f"component '{name}' has contradictory before/depends_on for: "
                + ", ".join(overlap_before_dep)
            )

        p_self = int(recs[name].priority)
        for pred in sorted(dep | aft):
            p_pred = int(recs[pred].priority)
            if p_self < p_pred:
                raise ComponentOrderError(
                    f"priority conflict: '{name}'(priority={p_self}) declares after/depends_on '{pred}'"
                    f"(priority={p_pred})"
                )
        for target in sorted(bef):
            p_target = int(recs[target].priority)
            if p_self > p_target:
                raise ComponentOrderError(
                    f"priority conflict: '{name}'(priority={p_self}) declares before '{target}'"
                    f"(priority={p_target})"
                )
