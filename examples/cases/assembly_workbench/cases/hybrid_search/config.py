"""仅声明用户选择；种群大小、精英数和母池历史容量不是一回事。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class HybridConfig:
    seed: int = 23
    population_size: int = 6
    ga_steps: int = 2
    elite_count: int = 2
    local_steps: int = 2
    rounds: int = 2
    ga_sigma: float = 0.12
    vns_sigma: float = 0.06
    bias_weight: float = 0.15
    evaluation_budget: int = 80
    evaluation_mode: str = "problem"
    output_dir: str | None = None
    checkpoint_every: int = 4

    def __post_init__(self):
        for key in ("population_size", "ga_steps", "elite_count", "local_steps", "rounds",
                    "evaluation_budget", "checkpoint_every"):
            if type(getattr(self, key)) is not int or getattr(self, key) < 1:
                raise ValueError(f"{key} must be a positive integer")
        if self.population_size < 2 or self.elite_count > self.population_size:
            raise ValueError("population_size >= 2 and elite_count <= population_size are required")
        if self.ga_sigma <= 0 or self.vns_sigma <= 0 or self.bias_weight < 0:
            raise ValueError("mutation scales must be positive and bias_weight nonnegative")
        if self.evaluation_mode not in {"problem", "provider"}:
            raise ValueError("evaluation_mode must be problem or provider")

    @property
    def max_steps(self):
        # 留一次空尝试报告计划完成；不会因此多记一个逻辑步骤。
        return self.rounds * (self.ga_steps + self.elite_count * self.local_steps + 1) + 1
