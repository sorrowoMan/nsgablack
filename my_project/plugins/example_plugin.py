# -*- coding: utf-8 -*-
"""示例插件：用于快速验证插件接入和 context 写入。"""

from __future__ import annotations

from typing import Any, Dict

from nsgablack.plugins.base import Plugin
from nsgablack.utils.context.context_keys import KEY_GENERATION

KEY_PROJECT_HEARTBEAT_COUNT = "project.heartbeat.count"
KEY_PROJECT_HEARTBEAT_LAST_GEN = "project.heartbeat.last_generation"


class GenerationHeartbeatPlugin(Plugin):
    """每隔 N 代写一次心跳信息。"""

    context_requires = (KEY_GENERATION,)
    context_provides = (KEY_PROJECT_HEARTBEAT_COUNT, KEY_PROJECT_HEARTBEAT_LAST_GEN)
    context_mutates = (KEY_PROJECT_HEARTBEAT_COUNT, KEY_PROJECT_HEARTBEAT_LAST_GEN)
    context_cache = ()
    context_notes = (
        "将心跳计数和最近触发代数写入 context，便于联调与可视化检查。",
    )

    def __init__(self, interval: int = 5, verbose: bool = True) -> None:
        super().__init__(name="project_heartbeat")
        self.interval = max(1, int(interval))
        self.verbose = bool(verbose)
        self._hits = 0
        self._last_generation = 0

    def on_solver_init(self, solver) -> None:
        self._hits = 0
        self._last_generation = 0

    def on_generation_end(self, generation: int) -> None:
        generation = int(generation)
        if generation % self.interval != 0:
            return None
        self._hits += 1
        self._last_generation = generation
        if self.verbose:
            print(
                f"[heartbeat] gen={generation} hits={self._hits} interval={self.interval}",
            )
        return None

    def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # 将当前心跳状态投影到 context，供 Inspector/其他组件读取
        context[KEY_PROJECT_HEARTBEAT_COUNT] = int(self._hits)
        context[KEY_PROJECT_HEARTBEAT_LAST_GEN] = int(self._last_generation)
        context.setdefault(KEY_GENERATION, int(getattr(self.solver, "generation", 0)))
        return context

    def on_solver_finish(self, result: Dict[str, Any]) -> None:
        result["project_heartbeat"] = {
            "hits": int(self._hits),
            "interval": int(self.interval),
            "last_generation": int(self._last_generation),
        }
