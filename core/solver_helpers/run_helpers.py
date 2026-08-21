"""Run helper utilities for SolverBase."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Mapping, Optional

from blackbase.plugin import report_soft_error
from .result_helpers import format_run_result

logger = logging.getLogger(__name__)


def _control_context(solver: Any, context: Any) -> dict[str, Any]:
    if isinstance(context, Mapping):
        return dict(context)
    for name in ("get_context", "build_context"):
        getter = getattr(solver, name, None)
        if not callable(getter):
            continue
        try:
            return dict(getter() or {})
        except Exception:
            continue
    return {}


def _request_stop(solver: Any) -> None:
    request = getattr(solver, "request_stop", None)
    if callable(request):
        request()
    else:
        setattr(solver, "stop_requested", True)


def _apply_resolved_decisions(solver: Any, resolved: Any, context: Mapping[str, Any]) -> None:
    if not isinstance(resolved, Mapping):
        return
    setattr(solver, "last_control_decisions", dict(resolved))
    generic_handler = getattr(solver, "apply_control_decision", None)
    for domain, decision in resolved.items():
        if callable(generic_handler):
            generic_handler(decision)
        else:
            domain_handler = getattr(solver, f"apply_{str(domain)}_control", None)
            if callable(domain_handler):
                domain_handler(decision)
        payload = dict(getattr(decision, "payload", {}) or {})
        # A stop request has the same meaning regardless of the arbitration
        # domain that produced it (for example budget or stopping).
        if bool(payload.get("stop", False)):
            _request_stop(solver)

def apply_runtime_control_slot(solver: Any, *, slot: str, value: Any = None, context: Any = None) -> Any:
    """Apply a runtime control slot through the solver runtime controller."""
    controller = getattr(solver, "runtime_controller", None)
    if controller is None:
        return value
    apply_fn = getattr(controller, "apply_slot", None)
    if callable(apply_fn):
        return apply_fn(solver, slot=str(slot), value=value, context=context)
    run_fn = getattr(controller, "run_slot", None)
    if callable(run_fn):
        return run_fn(str(slot), value, context=context)
    resolve_fn = getattr(controller, "resolve", None)
    if not callable(resolve_fn):
        return value
    ctx = _control_context(solver, context)
    try:
        resolved = resolve_fn(solver, slot=str(slot), context=ctx)
        _apply_resolved_decisions(solver, resolved, ctx)
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
    return value


def _call_optional(obj: Any, name: str, *args: Any) -> None:
    fn = getattr(obj, name, None)
    if callable(fn):
        fn(*args)


def _checkpoint_case_runtime(solver: Any) -> None:
    checkpoint = getattr(solver, "checkpoint_case_runtime", None)
    if callable(checkpoint):
        checkpoint()
        return
    runtime_checkpoint = getattr(getattr(solver, "case_runtime", None), "checkpoint", None)
    if callable(runtime_checkpoint):
        runtime_checkpoint()


def run_solver_loop(
    solver: Any,
    *,
    max_steps: Optional[int] = None,
    max_generations: Optional[int] = None,
    callback: Optional[Callable[[Any], bool]] = None,
) -> Any:
    """Run the SolverBase lifecycle loop."""
    limit = max_steps if max_steps is not None else max_generations
    if limit is None:
        limit = getattr(solver, "max_steps", 1)
    limit = max(0, int(limit))
    solver.max_steps = limit
    solver.running = True
    solver.stop_requested = False
    solver.stop_reason = None
    solver.start_time = time.time()
    result: dict[str, Any] = {}
    steps_executed = 0
    termination_reason = "step_limit"
    primary_error: BaseException | None = None
    completed_result: Any = None
    setattr(solver, "_runtime_setup_complete", False)

    try:
        _checkpoint_case_runtime(solver)
        prepare_fresh_run = getattr(solver, "prepare_fresh_run", None)
        if callable(prepare_fresh_run):
            prepare_fresh_run()
        else:
            set_generation = getattr(solver, "set_generation", None)
            if callable(set_generation):
                set_generation(0)
            else:
                solver.generation = 0
            solver.evaluation_count = 0
            solver.reset_evaluation_budget()
        solver.setup()
        setattr(solver, "_runtime_setup_complete", True)
        _call_optional(solver, "_apply_pending_restore_envelopes")
        _checkpoint_case_runtime(solver)
        _call_optional(solver.plugin_manager, "on_solver_init", solver)
        _call_optional(solver, "_runtime_governance_on_solver_init")
        resume_loaded = bool(getattr(solver, "_resume_loaded", False))
        if resume_loaded:
            start_step = max(
                0,
                int(getattr(solver, "_resume_cursor", getattr(solver, "generation", 0)) or 0),
            )
        else:
            start_step = 0
            _call_optional(solver, "_initialize_run_state")
        setattr(solver, "_resume_loaded", False)
        setattr(solver, "_resume_cursor", 0)
        _call_optional(solver, "_start_run_progress_clock")

        for step_index in range(start_step, limit):
            _checkpoint_case_runtime(solver)
            set_generation = getattr(solver, "set_generation", None)
            if callable(set_generation):
                set_generation(step_index)
            else:
                solver.generation = step_index
            generation = int(step_index)
            if bool(getattr(solver, "stop_requested", False)):
                termination_reason = str(
                    getattr(solver, "stop_reason", None) or "user_stop"
                )
                break
            _call_optional(solver, "_apply_pending_plugin_order_updates")
            control = getattr(solver, "_apply_runtime_control_slot", None)
            if callable(control):
                control("gen_start")
            if bool(getattr(solver, "stop_requested", False)):
                termination_reason = str(
                    getattr(solver, "stop_reason", None) or "user_stop"
                )
                break
            should_execute = getattr(solver, "should_execute_step", None)
            if callable(should_execute) and not bool(should_execute(generation)):
                if not bool(getattr(solver, "stop_requested", False)):
                    request_stop = getattr(solver, "request_stop", None)
                    if callable(request_stop):
                        request_stop("pre_step_policy")
                termination_reason = str(
                    getattr(solver, "stop_reason", None) or "pre_step_policy"
                )
                break
            _call_optional(solver.plugin_manager, "on_generation_start", generation)
            _checkpoint_case_runtime(solver)
            solver.step()
            _checkpoint_case_runtime(solver)
            steps_executed += 1
            _call_optional(solver, "_record_completed_run_step")
            _call_optional(solver.plugin_manager, "on_step", solver, generation)
            _call_optional(solver.plugin_manager, "on_generation_end", generation)
            _call_optional(solver, "_runtime_governance_on_generation_end", generation)
            if callable(control):
                control("gen_end")
            if callback is not None and bool(callback(solver)):
                termination_reason = "callback"
                break
            if bool(getattr(solver, "stop_requested", False)):
                termination_reason = str(
                    getattr(solver, "stop_reason", None) or "user_stop"
                )
                break

        elapsed = max(
            0.0,
            float(time.time() - float(getattr(solver, "start_time", time.time()))),
        )
        total_steps = int(start_step) + int(steps_executed)
        set_generation = getattr(solver, "set_generation", None)
        if callable(set_generation):
            set_generation(total_steps)
        else:
            solver.generation = total_steps
        result.update(
            {
                "status": (
                    "ok"
                    if not bool(getattr(solver, "stop_requested", False))
                    else "stopped"
                ),
                "termination_reason": termination_reason,
                "generation": int(total_steps),
                "steps": int(total_steps),
                "steps_executed": int(steps_executed),
                "resume_from": int(start_step) if resume_loaded else 0,
                "evaluation_count": int(
                    getattr(solver, "evaluation_count", 0) or 0
                ),
                "elapsed_sec": elapsed,
                "logical_run_steps": int(
                    getattr(solver, "run_progress_steps", total_steps)
                ),
                "logical_run_elapsed_sec": float(
                    getattr(solver, "run_progress_elapsed_seconds", elapsed)
                ),
            }
        )
        builder = getattr(solver, "_build_run_result", None)
        if callable(builder):
            result = builder(result)
        else:
            result = format_run_result(
                solver=solver,
                base_result=result,
                return_dict=True,
            )
        finalizer = getattr(solver, "finalize_run_result", None)
        if callable(finalizer):
            finalized = finalizer(result)
            if finalized is not None:
                result = finalized
        setattr(solver, "last_result", result)
        _checkpoint_case_runtime(solver)
        _call_optional(solver, "_runtime_governance_on_solver_finish", result)
        _call_optional(solver.plugin_manager, "on_solver_finish", result)
        completed_result = result
    except BaseException as exc:
        primary_error = exc
        dispatcher = getattr(solver, "_dispatch_error_once", None)
        if callable(dispatcher):
            dispatcher(exc)
        elif not bool(getattr(exc, "_nsgablack_error_dispatched", False)):
            pm = getattr(solver, "plugin_manager", None)
            if pm is not None:
                error_context = dict(getattr(solver, "build_context", lambda: {})() or {})
                phase = getattr(exc, "_nsgablack_error_phase", None)
                if phase:
                    error_context["error_phase"] = str(phase)
                error_context.update(dict(getattr(exc, "_nsgablack_error_context", {}) or {}))
                pm.on_error(exc, error_context)
        raise
    finally:
        _call_optional(solver, "_pause_run_progress_clock")
        try:
            try:
                solver.teardown()
            except BaseException as teardown_error:
                if primary_error is None:
                    dispatcher = getattr(solver, "_dispatch_error_once", None)
                    if callable(dispatcher):
                        dispatcher(teardown_error)
                    raise
                cleanup_evidence = {
                    "type": type(teardown_error).__name__,
                    "message": str(teardown_error),
                }
                setattr(solver, "_teardown_error", cleanup_evidence)
                setattr(primary_error, "_nsgablack_teardown_error", cleanup_evidence)
                add_note = getattr(primary_error, "add_note", None)
                if callable(add_note):
                    add_note(
                        "Solver teardown also failed: "
                        f"{cleanup_evidence['type']}: {cleanup_evidence['message']}"
                    )
        finally:
            solver.running = False
            setattr(solver, "_runtime_setup_complete", False)

    if completed_result is None:  # pragma: no cover - guarded by lifecycle flow
        raise RuntimeError("solver lifecycle completed without a result")
    post_teardown = getattr(solver, "finalize_after_teardown", None)
    if callable(post_teardown):
        try:
            finalized = post_teardown(completed_result)
            if finalized is not None:
                completed_result = finalized
        except BaseException as exc:
            dispatcher = getattr(solver, "_dispatch_error_once", None)
            if callable(dispatcher):
                dispatcher(exc)
            raise
    setattr(solver, "last_result", completed_result)
    return completed_result


__all__ = [
    "apply_runtime_control_slot",
    "run_solver_loop",
]
