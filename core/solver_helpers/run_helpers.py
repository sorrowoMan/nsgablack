"""Run-loop helpers used by SolverBase."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional


def run_solver_loop(solver: Any, *, max_steps: Optional[int] = None) -> Dict[str, Any]:
    steps = int(max_steps if max_steps is not None else solver.max_steps)
    solver.running = True
    solver.stop_requested = False
    solver.start_time = time.time()

    solver.plugin_manager.on_solver_init(solver)
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
        solver.plugin_manager.on_generation_start(solver.generation)
        # Keep on_step semantics consistent even when subclasses override step().
        solver.plugin_manager.on_step(solver, solver.generation)
        solver.step()
        solver.plugin_manager.on_generation_end(solver.generation)
        executed_steps += 1

    solver.teardown()
    elapsed = time.time() - solver.start_time
    if executed_steps > 0:
        total_steps = int(solver.generation + 1)
    else:
        total_steps = int(start_step)
    result = {
        "status": "stopped" if solver.stop_requested else "completed",
        "steps": total_steps,
        "steps_executed": int(executed_steps),
        "resume_from": int(start_step) if resume_loaded else 0,
        "elapsed_sec": elapsed,
    }
    solver.plugin_manager.on_solver_finish(result)
    solver.running = False
    return result
