"""Run-loop helpers used by SolverBase."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from ...utils.engineering.error_policy import report_soft_error

logger = logging.getLogger(__name__)


def apply_runtime_control_slot(solver: Any, *, slot: str) -> None:
    runtime_controller = getattr(solver, "runtime_controller", None)
    if runtime_controller is None or not hasattr(runtime_controller, "resolve"):
        return
    context = {}
    getter = getattr(solver, "get_context", None)
    if callable(getter):
        try:
            context = dict(getter() or {})
        except Exception:
            context = {}
    try:
        resolved = runtime_controller.resolve(solver, slot=str(slot), context=context)
    except Exception as exc:
        if bool(getattr(solver, "plugin_strict", False)):
            raise
        report_soft_error(
            component="ControlPlane",
            event=f"runtime_control_slot.{slot}",
            exc=exc,
            logger=logger,
            context_store=getattr(solver, "context_store", None),
            strict=False,
            level="warning",
        )
        return
    stopping = resolved.get("stopping") if isinstance(resolved, dict) else None
    payload = dict(getattr(stopping, "payload", {}) or {}) if stopping is not None else {}
    if bool(payload.get("stop", False)):
        request_stop = getattr(solver, "request_stop", None)
        if callable(request_stop):
            request_stop()
        else:
            setattr(solver, "stop_requested", True)


def run_solver_loop(solver: Any, *, max_steps: Optional[int] = None) -> Dict[str, Any]:
    steps = int(max_steps if max_steps is not None else solver.max_steps)
    solver.running = True
    solver.stop_requested = False
    solver.start_time = time.time()

    solver.plugin_manager.on_solver_init(solver)
    governance_init = getattr(solver, "_runtime_governance_on_solver_init", None)
    if callable(governance_init):
        try:
            governance_init()
        except Exception:
            if bool(getattr(solver, "plugin_strict", False)):
                raise
    solver.setup()

    resume_loaded = bool(getattr(solver, "_resume_loaded", False))
    if resume_loaded:
        start_step = int(getattr(solver, "_resume_cursor", getattr(solver, "generation", 0)))
        start_step = max(0, start_step)
        try:
            solver.evaluation_count = int(getattr(solver, "evaluation_count", 0))
        except Exception:
            solver.evaluation_count = 0
    else:
        start_step = 0
        solver.generation = 0
        solver.evaluation_count = 0
    setattr(solver, "_resume_loaded", False)
    setattr(solver, "_resume_cursor", 0)

    executed_steps = 0
    for step_idx in range(start_step, steps):
        if solver.stop_requested:
            break
        solver.generation = step_idx
        apply_pending_order = getattr(solver, "_apply_pending_plugin_order_updates", None)
        if callable(apply_pending_order):
            apply_pending_order()
        apply_runtime_control_slot(solver, slot="gen_start")
        solver.plugin_manager.on_generation_start(solver.generation)
        solver.step()
        # Keep on_step semantics consistent even when subclasses override step().
        solver.plugin_manager.on_step(solver, solver.generation)
        solver.plugin_manager.on_generation_end(solver.generation)
        governance_gen_end = getattr(solver, "_runtime_governance_on_generation_end", None)
        if callable(governance_gen_end):
            try:
                governance_gen_end(int(solver.generation))
            except Exception:
                if bool(getattr(solver, "plugin_strict", False)):
                    raise
        apply_runtime_control_slot(solver, slot="gen_end")
        executed_steps += 1

    solver.teardown()
    elapsed = time.time() - solver.start_time
    if executed_steps > 0:
        total_steps = int(solver.generation + 1)
    else:
        total_steps = int(start_step)
    solver.generation = int(total_steps)
    result = {
        "status": "stopped" if solver.stop_requested else "completed",
        "steps": total_steps,
        "steps_executed": int(executed_steps),
        "resume_from": int(start_step) if resume_loaded else 0,
        "elapsed_sec": elapsed,
    }
    builder = getattr(solver, "_build_run_result", None)
    if callable(builder):
        try:
            built = builder(dict(result))
            if isinstance(built, dict):
                result = built
        except Exception:
            # Fall back to base result on builder errors.
            pass
    setattr(solver, "last_result", result)
    governance_finish = getattr(solver, "_runtime_governance_on_solver_finish", None)
    if callable(governance_finish):
        try:
            governance_finish(result)
        except Exception:
            if bool(getattr(solver, "plugin_strict", False)):
                raise
    solver.plugin_manager.on_solver_finish(result)
    solver.running = False
    return result
