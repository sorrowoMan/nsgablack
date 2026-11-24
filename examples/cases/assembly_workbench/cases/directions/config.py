"""算法规模与视图抽样；它们都不是解池容量。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DirectionsConfig:
    seed: int = 23
    directions: int = 3
    direction_sample: int | None = None
    refinement_layout: str = "serial"
    bootstrap_steps: int = 2
    local_steps: int = 2
    router_budget: int = 6
    output_dir: str | None = None

    def __post_init__(self):
        for name in ("seed", "directions", "bootstrap_steps", "local_steps", "router_budget"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.directions < 3 or self.bootstrap_steps < 2 or self.local_steps < 2:
            raise ValueError("this example needs three directions and baseline plus search updates")
        if self.router_budget < self.directions:
            raise ValueError("router_budget must fit the bootstrap population")
        if self.direction_sample is not None and (type(self.direction_sample) is not int
                or not 1 <= self.direction_sample <= self.directions):
            raise ValueError("direction_sample must be None or within the direction count")
        if self.output_dir is not None and (not isinstance(self.output_dir, str) or not self.output_dir.strip()):
            raise ValueError("output_dir must be a nonempty path string")
        if self.refinement_layout not in {"serial", "parallel"}:
            raise ValueError("refinement_layout must be serial or parallel")
        if self.refinement_layout == "parallel" and self.router_budget < max(4, 2 * self.selected_directions):
            raise ValueError("parallel router_budget must fit both poll proposals and all final returns")

    @property
    def selected_directions(self):
        return self.directions if self.direction_sample is None else self.direction_sample

    @property
    def max_steps(self):
        # Every seed gets its own baseline and local updates. Final winners
        # return together through one ordinary MOEA/D competition update.
        branches = 2 if self.refinement_layout == "serial" else 1
        return self.bootstrap_steps + branches * self.selected_directions * self.local_steps + 1
