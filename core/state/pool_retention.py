"""Candidate retention policy; it does not choose algorithm members."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PoolRetentionPolicy:
    """Retire unused rows after committed steps; keep recent restore roots.

    Explicitly pinned publications outlive the automatic publication window.
    Portable checkpoints contain their candidate values and remain independent
    of physical pool snapshots in the source store.
    """
    idle_steps: int = 20
    retained_publications: int = 2

    def __post_init__(self):
        if any(type(value) is not int or value < 1
               for value in (self.idle_steps, self.retained_publications)):
            raise ValueError("pool retention limits must be positive integers")
