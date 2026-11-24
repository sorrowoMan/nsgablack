"""本 Case 的显式参数；档案容量与求值批次分别声明。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ArchiveConfig:
    seed: int = 31
    batch_size: int = 5
    max_steps: int = 3
    output_dir: str | None = None

    def __post_init__(self):
        if any(type(getattr(self, name)) is not int or getattr(self, name) < 1
               for name in ("batch_size", "max_steps")):
            raise ValueError("batch_size/max_steps must be positive integers")
