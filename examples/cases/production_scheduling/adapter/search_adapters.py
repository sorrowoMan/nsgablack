"""Case-local search adapters for production_scheduling."""

from __future__ import annotations

from nsgablack.adapters import AlgorithmAdapter


class ProductionRandomSearchAdapter(AlgorithmAdapter):
    """Explorer: generate diverse feasible candidates via init+repair."""

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Generates candidates via solver init/repair hooks; no direct context mutation.",
    )

    def __init__(self, *, batch_size: int = 32):
        super().__init__(name="production_random_search")
        self.batch_size = int(batch_size)

    def propose(self, solver, context):
        out = []
        for _ in range(max(1, self.batch_size)):
            x = solver.init_candidate(context)
            x = solver.repair_candidate(x, context)
            out.append(x)
        return out


class ProductionLocalSearchAdapter(AlgorithmAdapter):
    """Exploiter: refine best solution via mutate+repair."""

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Refines candidates via solver mutate/repair hooks; no direct context mutation.",
    )

    def __init__(self, *, batch_size: int = 16):
        super().__init__(name="production_local_search")
        self.batch_size = int(batch_size)

    def propose(self, solver, context):
        base = solver.best_x
        out = []
        for _ in range(max(1, self.batch_size)):
            if base is None:
                x = solver.init_candidate(context)
            else:
                x = solver.mutate_candidate(base, context)
            x = solver.repair_candidate(x, context)
            out.append(x)
        return out
