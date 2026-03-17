# -*- coding: utf-8 -*-
"""Example plugin template with explicit context contract."""

from __future__ import annotations

from typing import Any, Dict

from nsgablack.plugins.base import Plugin
from nsgablack.core.state.context_keys import KEY_GENERATION

KEY_PROJECT_EXAMPLE_HIT = "project.example_plugin.hit_count"


class ExampleProjectPlugin(Plugin):
    """Minimal project plugin: count generation hits and expose a context key."""

    context_requires = (KEY_GENERATION,)
    context_provides = (KEY_PROJECT_EXAMPLE_HIT,)
    context_mutates = (KEY_PROJECT_EXAMPLE_HIT,)
    context_cache = ()
    context_notes = ("Demo plugin for scaffold: updates a project-level counter.",)

    def __init__(self, interval: int = 5, verbose: bool = True) -> None:
        super().__init__(name="project_example_plugin")
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
            print(f"[example_plugin] gen={generation} hit_count={self._hit_count}")
        return None

    def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
        context[KEY_PROJECT_EXAMPLE_HIT] = int(self._hit_count)
        return context

    def on_solver_finish(self, result: Dict[str, Any]) -> None:
        result["example_project_plugin"] = {
            "hit_count": int(self._hit_count),
            "interval": int(self.interval),
        }
