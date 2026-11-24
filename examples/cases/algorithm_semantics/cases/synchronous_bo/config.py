"""仅放本 Case 参数；不复制框架的组件注册实现。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class BOCaseConfig:
    max_steps: int = 4
    bias_weight: float = 0.0
    output_dir: str | None = None
    checkpoint_every: int = 1

    def __post_init__(self):
        if type(self.max_steps) is not int or self.max_steps < 1:
            raise ValueError("max_steps must be a positive integer")
        if type(self.checkpoint_every) is not int or self.checkpoint_every < 1:
            raise ValueError("checkpoint_every must be positive")
