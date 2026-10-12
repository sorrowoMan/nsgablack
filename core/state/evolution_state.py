"""Evolution-owned projections participating in the shared step transaction."""
from copy import deepcopy
from dataclasses import dataclass, field, fields
from typing import Any, ClassVar


@dataclass
class EvolutionState:
    name: ClassVar[str] = "solver.evolution"
    history: list = field(default_factory=list)
    pareto_solutions: Any = None
    pareto_objectives: Any = None
    pareto_population_snapshot: Any = None
    mutation_range: float = 0.0

    def snapshot_step_state(self):
        return {item.name: (getattr(self, item.name) if item.name == "pareto_population_snapshot"
                            else deepcopy(getattr(self, item.name))) for item in fields(self)}

    def restore_step_state(self, state):
        for item in fields(self):
            setattr(self, item.name, state[item.name] if item.name == "pareto_population_snapshot"
                    else deepcopy(state[item.name]))

    def commit_step_state(self, state):
        return None

    def step_transaction_children(self):
        return ()
