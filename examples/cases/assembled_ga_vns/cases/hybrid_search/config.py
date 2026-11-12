"""本 Case 的算法配置；池历史容量与这些参数无关。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DemoConfig:
    seed: int = 7
    population_size: int = 12
    ga_steps: int = 8
    local_steps: int = 6
    local_batch: int = 4
    ga_sigma: float = 0.45
    vns_sigma: float = 0.12
    refinement_source: str = "population"
    elite_count: int = 20
    evaluation_budget: int | None = None
    schedule: str = "phases"
    rounds: int = 2

    def __post_init__(self):
        for name in ("population_size", "ga_steps", "local_steps", "local_batch"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.population_size < 2 or self.ga_sigma <= 0 or self.vns_sigma <= 0:
            raise ValueError("population_size >= 2 and positive mutation scales are required")
        if self.refinement_source not in {"population", "elite"}:
            raise ValueError("refinement_source must be population or elite")
        if self.schedule not in {"phases", "plan"}:
            raise ValueError("schedule must be phases or plan")
        if type(self.rounds) is not int or self.rounds < 1:
            raise ValueError("rounds must be a positive integer")
        if type(self.elite_count) is not int or self.elite_count < 1:
            raise ValueError("elite_count must be a positive integer")
        if self.refinement_source == "elite" and self.elite_count > self.population_size:
            raise ValueError("elite_count cannot exceed population_size in elite mode")
        if self.evaluation_budget is not None and (
                type(self.evaluation_budget) is not int or self.evaluation_budget < 1):
            raise ValueError("evaluation_budget must be a positive integer or None")

    @property
    def refinement_count(self):
        return self.population_size if self.refinement_source == "population" else self.elite_count

    @property
    def max_steps(self):
        work = self.ga_steps + self.refinement_count * self.local_steps + 1
        # One spare logical allowance lets the finished plan report normal
        # completion on an empty attempt; it never manufactures another step.
        return self.rounds * work + 1 if self.schedule == "plan" else work

    @property
    def proposal_budget(self):
        # 返回池最多含全部局部接纳提案，最后一次竞争不悄悄裁掉输入。
        return max(self.population_size,
                   self.refinement_count * (1 + (self.local_steps - 1) * self.local_batch))
