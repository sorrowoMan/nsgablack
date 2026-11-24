"""只处理候选可行性；不选择成员、不求值、不访问算法 Unit。"""
from typing import ClassVar

import numpy as np
from blackbase.representation import RepresentationCapabilities
from nsgablack.representation.base import RepresentationComponentContract


class RecipeRepair(RepresentationComponentContract):
    representation_capabilities: ClassVar = RepresentationCapabilities(
        frozenset({"repair"}), repair_idempotent=True)
    state_recovery_level = "L1"
    state_recovery_notes = "Restores detached observation counters; the repair itself is deterministic."
    context_notes = "Clips box bounds and projects total recipe amount to 1.2."

    def __init__(self):
        self.calls = self.changed = 0

    def repair(self, candidate, context=None):
        before = np.asarray(candidate, dtype=float)
        result = np.clip(before, 0., 1.)
        if float(result.sum()) > 1.2:
            result *= 1.2 / float(result.sum())
        self.calls += 1
        self.changed += int(not np.array_equal(before, result))
        return result

    def validate(self, candidate, context=None):
        x = np.asarray(candidate, dtype=float)
        return bool(x.shape == (2,) and np.all(np.isfinite(x)) and np.all(x >= -1e-12)
                    and np.all(x <= 1. + 1e-12) and x.sum() <= 1.2 + 1e-12)

    def get_state(self):
        return {"schema": "assembly_workbench.recipe_repair/v1", "calls": self.calls,
                "changed": self.changed}

    def set_state(self, state):
        if (state.get("schema") != "assembly_workbench.recipe_repair/v1"
                or type(state.get("calls")) is not int or type(state.get("changed")) is not int
                or not 0 <= state["changed"] <= state["calls"]):
            raise ValueError("invalid recipe repair observation state")
        self.calls, self.changed = state["calls"], state["changed"]
