# -*- coding: utf-8 -*-
# Plugin template: copy and customize lifecycle hooks.

from __future__ import annotations

from typing import Any, Dict

from nsgablack.plugins.base import Plugin
from nsgablack.core.state.context_keys import KEY_GENERATION

KEY_PROJECT_PLUGIN_TEMPLATE = "project.plugin_template.hit_count"


class PluginTemplate(Plugin):
    # Minimal runnable plugin template.

    context_requires = (KEY_GENERATION,)
    context_provides = (KEY_PROJECT_PLUGIN_TEMPLATE,)
    context_mutates = (KEY_PROJECT_PLUGIN_TEMPLATE,)
    context_cache = ()
    context_notes = ("Template plugin that exposes a small runtime counter.",)

    def __init__(self, interval: int = 5, verbose: bool = True) -> None:
        super().__init__(name="plugin_template")
        self.interval = max(1, int(interval))
        self.verbose = bool(verbose)
        self._hit_count = 0

    def on_solver_init(self, solver) -> None:
        self._hit_count = 0

    def on_generation_end(self, generation: int) -> None:
        generation = int(generation)
        if generation % self.interval != 0:
            return None
        self._hit_count += 1
        if self.verbose:
            print(f"[plugin_template] gen={generation} hit_count={self._hit_count}")
        return None

    def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
        context[KEY_PROJECT_PLUGIN_TEMPLATE] = int(self._hit_count)
        return context
