"""Safe compatibility bridge from elite Plugins to the Adapter wrapper."""

from __future__ import annotations

from typing import Any

from nsgablack.adapters import AlgorithmAdapter, EliteRetentionAdapter, EliteRetentionConfig
from nsgablack.plugins.base import Plugin

from .deprecation import warn_deprecated


_NEW_SYMBOL = "nsgablack.adapters.EliteRetentionAdapter"
_REMOVE_IN = "1.0.0"


class _ElitePluginCompat(Plugin):
    """Deprecated Plugin shell that installs the transactional Adapter wrapper."""

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Compatibility-only assembly bridge; population authority remains Adapter-owned.",
    )
    old_symbol = ""

    def __init__(self, *, name: str, adapter_config: EliteRetentionConfig) -> None:
        warn_deprecated(
            old=self.old_symbol,
            new=_NEW_SYMBOL,
            remove_in=_REMOVE_IN,
            stacklevel=3,
        )
        super().__init__(name)
        self._adapter_config = adapter_config
        self._wrapper: EliteRetentionAdapter | None = None

    @property
    def wrapped_adapter(self) -> EliteRetentionAdapter | None:
        return self._wrapper

    def attach(self, solver: Any) -> None:
        warn_deprecated(
            old=f"{self.old_symbol}.attach",
            new=f"{_NEW_SYMBOL} via solver.set_adapter(...) before solver.run()",
            remove_in=_REMOVE_IN,
            stacklevel=3,
        )
        super().attach(solver)
        self._install_wrapper(solver, inner_already_setup=False)

    def on_solver_init(self, solver: Any) -> None:
        # Solver.setup() precedes this hook.  This second check supports legacy
        # assembly that registered the Plugin before assigning its Adapter.
        self._install_wrapper(solver, inner_already_setup=True)

    def _install_wrapper(self, solver: Any, *, inner_already_setup: bool) -> None:
        current = getattr(solver, "adapter", None)
        if current is None or current is self._wrapper:
            return
        if not isinstance(current, AlgorithmAdapter):
            raise TypeError(
                f"{self.old_symbol} requires solver.adapter to be an AlgorithmAdapter"
            )

        wrapper = EliteRetentionAdapter(
            current,
            self._adapter_config,
            name=f"{self.name}_adapter",
        )
        if inner_already_setup:
            # The canonical run lifecycle has already called current.setup().
            # Initialize only wrapper-owned state to avoid setting up the inner
            # Adapter twice.
            wrapper._setup_local_state(solver)

        setter = getattr(solver, "set_adapter", None)
        if callable(setter):
            setter(wrapper)
        else:
            setattr(solver, "adapter", wrapper)
        self._wrapper = wrapper


class BasicElitePlugin(_ElitePluginCompat):
    """Deprecated bridge for the former basic elite-retention Plugin."""

    old_symbol = "nsgablack.plugins.BasicElitePlugin"

    def __init__(self, retention_prob: float = 0.9, retention_ratio: float = 0.1) -> None:
        self.retention_prob = float(retention_prob)
        self.retention_ratio = float(retention_ratio)
        super().__init__(
            name="basic_elite",
            adapter_config=EliteRetentionConfig(
                retention_probability=self.retention_prob,
                retention_ratio=self.retention_ratio,
                history_size=1,
                mutation_scale=0.01,
            ),
        )


class HistoricalElitePlugin(_ElitePluginCompat):
    """Deprecated bridge for the former historical elite-retention Plugin."""

    old_symbol = "nsgablack.plugins.HistoricalElitePlugin"

    def __init__(
        self,
        history_size: int = 50,
        replacement_prob: float = 0.1,
        replacement_ratio: float = 0.1,
    ) -> None:
        self.history_size = int(history_size)
        self.replacement_prob = float(replacement_prob)
        self.replacement_ratio = float(replacement_ratio)
        super().__init__(
            name="historical_elite",
            adapter_config=EliteRetentionConfig(
                retention_probability=self.replacement_prob,
                retention_ratio=self.replacement_ratio,
                history_size=self.history_size,
                mutation_scale=0.02,
            ),
        )


__all__ = ["BasicElitePlugin", "HistoricalElitePlugin"]
