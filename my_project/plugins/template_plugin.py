# -*- coding: utf-8 -*-
"""插件模板：复制后改文件名和类名即可开始开发。"""

from __future__ import annotations

from typing import Any, Dict

from nsgablack.plugins.base import Plugin
from nsgablack.core.state.context_keys import KEY_GENERATION

KEY_PROJECT_PLUGIN_TEMPLATE = "project.plugin_template.hit_count"


class PluginTemplate(Plugin):
    """最小可运行插件模板。"""

    context_requires = (KEY_GENERATION,)
    context_provides = (KEY_PROJECT_PLUGIN_TEMPLATE,)
    context_mutates = (KEY_PROJECT_PLUGIN_TEMPLATE,)
    context_cache = ()
    context_notes = ("插件模板：按固定代间隔记录命中次数，并写入 context。",)

    def __init__(self, interval: int = 5, verbose: bool = True) -> None:
        super().__init__(name="plugin_template")
        # interval：每隔多少代触发一次；verbose：是否打印日志
        self.interval = max(1, int(interval))
        self.verbose = bool(verbose)
        self._hit_count = 0

    def on_solver_init(self, solver) -> None:
        # 每次新 run 开始时重置内部状态
        self._hit_count = 0

    def on_generation_end(self, generation: int) -> None:
        # 代末触发：按 interval 统计命中次数
        generation = int(generation)
        if generation % self.interval != 0:
            return None
        self._hit_count += 1
        if self.verbose:
            print(f"[plugin_template] gen={generation} hit_count={self._hit_count}")
        return None

    def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # 将插件状态暴露到 context，便于 Inspector / 其他组件读取
        context[KEY_PROJECT_PLUGIN_TEMPLATE] = int(self._hit_count)
        return context
