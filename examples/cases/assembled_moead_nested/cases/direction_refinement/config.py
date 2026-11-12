"""本例只声明规模；不修改解池容量，也不建立另一套资源配置。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DemoConfig:
    seed: int = 23
    directions: int = 6
    bootstrap_steps: int = 2
    local_steps: int = 2
    neighborhood_batch: int = 2
    router_budget: int = 6

    def __post_init__(self):
        for name in ("directions", "bootstrap_steps", "local_steps", "neighborhood_batch", "router_budget"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.directions < 2 or self.local_steps < 2 or self.bootstrap_steps < 2:
            raise ValueError("this teaching example requires at least two directions, bootstrap and local steps")
        if self.router_budget < self.directions or self.router_budget < self.neighborhood_batch:
            raise ValueError("router_budget must fit bootstrap and a complete neighborhood")

    @property
    def local_evaluations(self):
        return self.directions * (1 + (self.local_steps - 1) * self.neighborhood_batch)

    @property
    def return_steps(self):
        return (self.local_evaluations + self.router_budget - 1) // self.router_budget

    @property
    def max_steps(self):
        return self.bootstrap_steps + 2 * self.directions * self.local_steps + self.return_steps
