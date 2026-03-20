"""Shared base for evaluation-provider plugins."""

from __future__ import annotations

from typing import Any, Optional

from ..base import Plugin



class EvaluationProviderPluginBase(Plugin):
    """Plugin base that auto-registers an evaluation provider on attach."""
    # 明确声明 context contract 字段（如无需求可为空元组，便于合规与后续扩展）
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()

    def __init__(self, name: str, *, priority: int = 0) -> None:
        super().__init__(name=str(name), priority=int(priority))
        self._provider: Optional[Any] = None

    def attach(self, solver) -> None:
        super().attach(solver)
        if self._provider is None:
            self._provider = self.create_provider()
        register = getattr(solver, "register_evaluation_provider", None)
        if callable(register) and self._provider is not None:
            register(self._provider)

    def detach(self) -> None:
        provider = self._provider
        self._provider = None
        solver = getattr(self, "solver", None)
        unregister = getattr(solver, "unregister_evaluation_provider", None) if solver is not None else None
        if callable(unregister) and provider is not None:
            try:
                unregister(provider)
            except Exception:
                pass
        super().detach()

