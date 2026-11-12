from dataclasses import dataclass


@dataclass(frozen=True)
class CMASettings:
    seed: int = 19
    max_steps: int = 3
    fixture: str | None = None
    output_dir: str | None = None
    evaluation_budget: int | None = None

    def __post_init__(self):
        if type(self.max_steps) is not int or self.max_steps < 1:
            raise ValueError("max_steps must be a positive integer")
        if self.fixture not in {None, "scalar", "matrix"}:
            raise ValueError("fixture must be None, scalar or matrix")
