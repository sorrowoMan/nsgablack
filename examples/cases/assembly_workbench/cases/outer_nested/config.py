"""外层规模与超时；内层条件通过正式调用 payload 交付。"""
from dataclasses import dataclass

@dataclass(frozen=True)
class DemoConfig:
    seed: int = 43
    steps: int = 2
    inner_steps: int = 2

    def __post_init__(self):
        if any(type(value) is not int or value < 1 for value in (self.steps, self.inner_steps)):
            raise ValueError("steps and inner_steps must be positive integers")
