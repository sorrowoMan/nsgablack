"""内层运行规模；问题条件只通过 inner_task_payload 交付。"""
from dataclasses import dataclass

@dataclass(frozen=True)
class DemoConfig:
    seed: int = 41
    steps: int = 2

    def __post_init__(self):
        if type(self.steps) is not int or self.steps < 1:
            raise ValueError("steps must be a positive integer")
