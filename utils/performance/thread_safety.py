from __future__ import annotations

import threading
from typing import Optional

import numpy as np


class ThreadLocalRNG:
    """每线程独立 RNG（避免使用全局 np.random 带来的数据竞争与不可复现）。

    用法：
        rng = ThreadLocalRNG(seed=123)
        x = rng.random(10)

    说明：
    - 每个线程会 lazily 创建自己的 Generator。
    - 同一线程内可复现；跨线程顺序不保证（并行本身就会改变调度）。
    """

    def __init__(self, seed: Optional[int] = None):
        self._seed = None if seed is None else int(seed)
        self._local = threading.local()

    def _get_rng(self) -> np.random.Generator:
        rng = getattr(self._local, "rng", None)
        if rng is None:
            rng = np.random.default_rng(self._seed)
            self._local.rng = rng
        return rng

    def __getattr__(self, item):
        return getattr(self._get_rng(), item)
