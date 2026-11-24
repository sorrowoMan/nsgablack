"""Select committed views by their creating Adapter instance.

Native publishers (MOEA/D) and refiners with an explicit projected PoolTask
output use the same selector. Selection freezes the currently published set;
phase scheduling, not this selector, waits for all upstream work to finish.
"""
from __future__ import annotations

from dataclasses import dataclass


def adapter_path(root, target):
    """Resolve instance identity through the explicit transaction ownership tree."""
    found, seen = [], set()
    def visit(adapter, path):
        if id(adapter) in seen:
            raise ValueError("subpool creators require unambiguous Adapter instance ownership")
        seen.add(id(adapter))
        if adapter is target:
            found.append(path)
        for index, child in enumerate(adapter.step_transaction_children()):
            visit(child, (*path, f"{index}:{child.name}"))
    visit(root, (root.name,))
    if len(found) != 1:
        raise ValueError("subpool creator is not an instance in this Solver's Adapter tree")
    return found[0]


@dataclass(frozen=True)
class SubpoolSelection:
    creator: object
    count: int | None = None
    kind: str | None = None

    def __post_init__(self):
        from .algorithm_adapter import AlgorithmAdapter
        if not isinstance(self.creator, AlgorithmAdapter):
            raise TypeError("subpool selector requires an Adapter instance")
        if self.kind not in {None, "candidate_collection", "candidate_view", "objective_projection"}:
            raise ValueError("unsupported subpool selection kind")
        if self.count is not None and (type(self.count) is not int or self.count < 1):
            raise ValueError("random subpool count must be a positive integer")

    def identity(self):
        typ = type(self.creator)
        result = dict(creator_name=self.creator.name,
                    creator_type=f"{typ.__module__}.{typ.__qualname__}", count=self.count)
        if self.kind is not None:
            result["kind"] = self.kind
        return result


class _Subpools:
    def all(self, adapter, *, kind=None):
        return SubpoolSelection(adapter, kind=kind)

    def random(self, count, adapter, *, kind=None):
        return SubpoolSelection(adapter, count, kind)


subpools = _Subpools()

__all__ = ["subpools", "SubpoolSelection"]
