"""
Strategy chain adapter (macro-serial, micro-single).

Use cases:
- Simple sequential phases: NSGA2 -> VNS -> TR
- Serial groups: each phase can be a StrategyRouterAdapter
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from ..algorithm_adapter import AlgorithmAdapter
from ...utils.context.context_keys import KEY_PHASE, KEY_STRATEGY, KEY_STRATEGY_ID


PhaseAdapter = Union[AlgorithmAdapter, Callable[[], AlgorithmAdapter], Callable[[int], AlgorithmAdapter]]
AdvanceWhenFn = Callable[[Dict[str, Any]], bool]


@dataclass
class SerialPhaseSpec:
    name: str
    adapter: PhaseAdapter
    steps: int = -1  # -1 means "until end"
    advance_when: Optional[AdvanceWhenFn] = None
    enabled: bool = True


@dataclass
class SerialStrategyConfig:
    # List of (phase_name, steps) pairs; steps=-1 means "until end".
    phase_schedule: Tuple[Tuple[str, int], ...] = ()
    # If True, keep the last phase active after schedule end.
    repeat_last: bool = True


class StrategyChainAdapter(AlgorithmAdapter):
    """
    Serial controller for strategy phases.

    Each phase is a single child adapter (which can itself be a multi-strategy controller).
    """

    context_requires = ("generation",)
    context_provides = (KEY_PHASE, KEY_STRATEGY, KEY_STRATEGY_ID)
    context_mutates = ()
    context_cache = ()
    context_notes = ("Serial phase scheduler; delegates propose/update to active adapter.",)
    state_recovery_level = "L2"
    state_recovery_notes = "Restores current phase index, per-phase step counter, and child adapter states."

    def __init__(
        self,
        phases: Optional[Sequence[SerialPhaseSpec]] = None,
        *,
        config: Optional[SerialStrategyConfig] = None,
        name: str = "serial_strategy_controller",
        priority: int = 0,
        **config_kwargs,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.config = self.resolve_config(
            config=config,
            config_cls=SerialStrategyConfig,
            config_kwargs=config_kwargs,
            adapter_name="StrategyChainAdapter",
        )
        self.cfg = self.config
        self.phases: List[SerialPhaseSpec] = list(phases or [])
        self._adapters: List[AlgorithmAdapter] = []
        self._phase_steps: List[int] = []
        self._current_idx: int = 0
        self._step_in_phase: int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def setup(self, solver: Any) -> None:
        self._materialize_adapters()
        self._phase_steps = [int(p.steps) for p in self.phases]
        self._current_idx = 0
        self._step_in_phase = 0
        if self._adapters:
            self._adapters[self._current_idx].setup(solver)

    def teardown(self, solver: Any) -> None:
        for adapter in self._adapters:
            try:
                adapter.teardown(solver)
            except Exception:
                continue

    # ------------------------------------------------------------------
    # Propose/Update
    # ------------------------------------------------------------------
    def propose(self, solver: Any, context: Dict[str, Any]):
        adapter = self._current_adapter()
        if adapter is None:
            return []
        ctx = dict(context or {})
        ctx[KEY_PHASE] = self._current_phase_name()
        ctx[KEY_STRATEGY] = adapter.name
        ctx[KEY_STRATEGY_ID] = int(self._current_idx)
        return adapter.propose(solver, ctx)

    def update(
        self,
        solver: Any,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> None:
        adapter = self._current_adapter()
        if adapter is None:
            return
        ctx = dict(context or {})
        # Provide commonly-needed runtime fields for advance_when.
        try:
            ctx.setdefault("generation", int(getattr(solver, "generation", 0)))
        except Exception:
            pass
        try:
            if "best_objective" not in ctx:
                ctx["best_objective"] = getattr(solver, "best_objective", None)
        except Exception:
            pass
        try:
            if "best_x" not in ctx:
                ctx["best_x"] = getattr(solver, "best_x", None)
        except Exception:
            pass
        try:
            if "evaluation_count" not in ctx:
                ctx["evaluation_count"] = getattr(solver, "evaluation_count", None)
        except Exception:
            pass
        ctx[KEY_PHASE] = self._current_phase_name()
        ctx[KEY_STRATEGY] = adapter.name
        ctx[KEY_STRATEGY_ID] = int(self._current_idx)
        adapter.update(solver, candidates, objectives, violations, ctx)

        self._step_in_phase += 1
        if self._should_advance(ctx):
            self._advance_phase(solver)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def get_state(self) -> Dict[str, Any]:
        state = {
            "current_idx": int(self._current_idx),
            "step_in_phase": int(self._step_in_phase),
            "phase_steps": list(self._phase_steps),
            "phase_names": [p.name for p in self.phases],
            "adapters": [],
        }
        for adapter in self._adapters:
            try:
                state["adapters"].append(adapter.get_state())
            except Exception:
                state["adapters"].append({})
        return state

    def set_state(self, state: Dict[str, Any]) -> None:
        self._materialize_adapters()
        self._current_idx = int(state.get("current_idx", 0))
        self._step_in_phase = int(state.get("step_in_phase", 0))
        self._phase_steps = list(state.get("phase_steps", self._phase_steps))
        adapter_states = state.get("adapters", [])
        for adapter, astate in zip(self._adapters, adapter_states):
            try:
                adapter.set_state(dict(astate or {}))
            except Exception:
                continue

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _materialize_adapters(self) -> None:
        if self._adapters:
            return
        enabled = [p for p in self.phases if bool(p.enabled)]
        self.phases = enabled
        for idx, phase in enumerate(self.phases):
            adapter = phase.adapter
            if isinstance(adapter, AlgorithmAdapter):
                self._adapters.append(adapter)
            elif callable(adapter):
                try:
                    self._adapters.append(adapter(idx))
                except TypeError:
                    self._adapters.append(adapter())
            else:
                raise TypeError("phase.adapter must be AlgorithmAdapter or factory")

        if not self.phases:
            self._adapters = []

    def _current_adapter(self) -> Optional[AlgorithmAdapter]:
        if not self._adapters:
            return None
        idx = max(0, min(int(self._current_idx), len(self._adapters) - 1))
        return self._adapters[idx]

    def _current_phase_name(self) -> str:
        if not self.phases:
            return "phase_0"
        idx = max(0, min(int(self._current_idx), len(self.phases) - 1))
        return str(self.phases[idx].name)

    def _should_advance(self, ctx: Dict[str, Any]) -> bool:
        if not self.phases:
            return False
        idx = max(0, min(int(self._current_idx), len(self.phases) - 1))
        cond = self.phases[idx].advance_when
        if callable(cond):
            try:
                if bool(cond(dict(ctx))):
                    return True
            except Exception:
                pass
        steps = int(self._phase_steps[idx]) if idx < len(self._phase_steps) else int(self.phases[idx].steps)
        if steps < 0:
            return False
        return self._step_in_phase >= steps

    def _advance_phase(self, solver: Any) -> None:
        if not self.phases:
            return
        old_idx = int(self._current_idx)
        next_idx = old_idx + 1
        if next_idx >= len(self.phases):
            if not self.cfg.repeat_last:
                return
            next_idx = len(self.phases) - 1
        if next_idx == old_idx:
            self._step_in_phase = 0
            return
        try:
            self._adapters[old_idx].teardown(solver)
        except Exception:
            pass
        self._current_idx = next_idx
        self._step_in_phase = 0
        try:
            self._adapters[self._current_idx].setup(solver)
        except Exception:
            pass
