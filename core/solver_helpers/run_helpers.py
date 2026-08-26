"""Run helper utilities for SolverBase."""

from __future__ import annotations

import logging
import sys
import time
from typing import Any, Callable, Mapping, Optional

from blackbase.plugin import (
    ATTEMPT_END,
    ATTEMPT_START,
    GENERATION_COMMITTED,
    GENERATION_END,
    GENERATION_START,
    PluginLifecycleDispatchError,
    PluginLifecycleReceipt,
)

from blackbase.plugin import report_soft_error
from blackbase.project import attach_failure_evidence
from .result_helpers import format_run_result
from ..state.step_outcome import StepOutcome

logger = logging.getLogger(__name__)


class LifecycleCleanupError(RuntimeError):
    """One or more lifecycle end notifications failed after all were attempted."""

    def __init__(self, errors: list[tuple[str, BaseException]]) -> None:
        self.errors = tuple(errors)
        summary = "; ".join(
            f"{name}: {type(exc).__name__}: {exc}" for name, exc in errors
        )
        super().__init__(f"lifecycle cleanup failed: {summary}")


def _finish_lifecycle_participants(
    callbacks: list[tuple[str, Callable[[], None]]],
) -> None:
    """Run every matching end hook and preserve primary/secondary failures."""

    active_error = sys.exc_info()[1]
    cleanup_errors: list[tuple[str, BaseException]] = []
    for name, callback in callbacks:
        try:
            callback()
        except BaseException as exc:
            cleanup_errors.append((name, exc))
    if not cleanup_errors:
        return
    if active_error is None:
        raise LifecycleCleanupError(cleanup_errors) from cleanup_errors[0][1]
    evidence = tuple(
        {
            "participant": name,
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        for name, exc in cleanup_errors
    )
    try:
        setattr(active_error, "lifecycle_cleanup_errors", evidence)
    except Exception:
        pass
    try:
        attach_failure_evidence(
            active_error,
            "nsgablack_lifecycle_cleanup",
            evidence,
        )
    except Exception:
        pass
    add_note = getattr(active_error, "add_note", None)
    if callable(add_note):
        add_note(f"secondary lifecycle cleanup failures: {evidence!r}")
    for name, exc in cleanup_errors:
        logger.error(
            "Secondary lifecycle cleanup failure in %s",
            name,
            exc_info=(type(exc), exc, exc.__traceback__),
        )


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
    max_step_attempts: Optional[int] = None,
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
    step_attempts_executed = 0
    resume_attempts_from = 0
    last_step_outcome: StepOutcome | None = None
    termination_reason = "step_limit"
    primary_error: BaseException | None = None
    completed_result: Any = None
    run_plugin_receipt = PluginLifecycleReceipt.capture("on_solver_init", ())
    run_finish_attempted = False
    runtime_governance_started = False
    setattr(solver, "_run_plugin_receipt", run_plugin_receipt)
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
        setattr(solver, "_restore_collection_active", True)
        try:
            _call_optional(solver.plugin_manager, "prepare_restore", solver)
        finally:
            setattr(solver, "_restore_collection_active", False)
        _call_optional(solver, "_apply_pending_restore_envelopes")
        if bool(getattr(solver, "_resume_loaded", False)):
            _call_optional(solver, "reconcile_evaluation_evidence")
        _call_optional(solver, "_merge_run_progress_deadline_with_case_control")
        _checkpoint_case_runtime(solver)
        try:
            received = solver.plugin_manager.on_solver_init(solver)
        except PluginLifecycleDispatchError as exc:
            run_plugin_receipt = exc.receipt
            setattr(solver, "_run_plugin_receipt", run_plugin_receipt)
            raise
        if isinstance(received, PluginLifecycleReceipt):
            run_plugin_receipt = received
            setattr(solver, "_run_plugin_receipt", run_plugin_receipt)
        _call_optional(solver, "_runtime_governance_on_solver_init")
        runtime_governance_started = True
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
        resume_attempts_from = int(
            getattr(solver, "run_progress_attempts", 0) or 0
        )
        configured_attempt_limit = (
            max_step_attempts
            if max_step_attempts is not None
            else getattr(solver, "max_step_attempts", None)
        )
        attempt_limit = (
            max(0, int(configured_attempt_limit))
            if configured_attempt_limit is not None
            else max(int(limit), int(limit) * 4)
        )
        idle_limit_value = getattr(
            solver,
            "max_consecutive_idle_attempts",
            None,
        )
        idle_limit = (
            None
            if idle_limit_value is None
            else max(0, int(idle_limit_value))
        )

        while int(start_step) + int(steps_executed) < int(limit):
            total_attempts = int(resume_attempts_from) + int(step_attempts_executed)
            if total_attempts >= attempt_limit:
                termination_reason = "attempt_limit"
                break
            if (
                idle_limit is not None
                and int(getattr(solver, "run_progress_consecutive_idle_attempts", 0) or 0)
                >= idle_limit
            ):
                termination_reason = "idle_attempt_limit"
                break
            _checkpoint_case_runtime(solver)
            step_index = int(start_step) + int(steps_executed)
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
            _call_optional(solver, "_apply_pending_plugin_order_updates")
            control = getattr(solver, "_apply_runtime_control_slot", None)
            step_attempts_executed += 1
            attempt_number = int(resume_attempts_from) + int(step_attempts_executed)
            attempt_payload: dict[str, Any] = {
                "status": "running",
                "committed": False,
            }
            attempt_plugin_receipt = PluginLifecycleReceipt.capture(
                "on_step_attempt_start",
                (),
            )
            generation_plugin_receipt = PluginLifecycleReceipt.capture(
                "on_generation_start",
                (),
            )
            generation_control_started = False
            control_started = False
            attempt_recorded = False
            try:
                try:
                    attempt_plugin_receipt = solver.plugin_manager.begin_lifecycle(
                        "on_step_attempt_start",
                        attempt_number,
                        generation,
                    )
                except PluginLifecycleDispatchError as exc:
                    attempt_plugin_receipt = exc.receipt
                    raise
                _checkpoint_case_runtime(solver)
                try:
                    if callable(control):
                        control_started = True
                        control(ATTEMPT_START)
                    if bool(getattr(solver, "stop_requested", False)):
                        step_outcome = StepOutcome(
                            status="cancelled",
                            stop_requested=True,
                            reason=str(
                                getattr(solver, "stop_reason", None)
                                or "runtime_control"
                            ),
                        )
                    else:
                        raw_step_outcome = solver.step()
                        step_outcome = StepOutcome.from_value(
                            raw_step_outcome,
                            allow_legacy=bool(
                                getattr(solver, "allow_legacy_step_outcomes", False)
                            ),
                        )
                except BaseException as exc:
                    _call_optional(solver, "_record_run_step_attempt", "failed")
                    attempt_recorded = True
                    attempt_payload = {
                        "status": "failed",
                        "committed": False,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                    raise
                last_step_outcome = step_outcome
                attempt_payload = step_outcome.as_dict()
                _call_optional(
                    solver,
                    "_record_run_step_attempt",
                    step_outcome.status,
                )
                attempt_recorded = True
                setattr(solver, "last_step_outcome", attempt_payload)
                _checkpoint_case_runtime(solver)
                if step_outcome.stop_requested and not bool(
                    getattr(solver, "stop_requested", False)
                ):
                    request_stop = getattr(solver, "request_stop", None)
                    if callable(request_stop):
                        request_stop(step_outcome.reason or step_outcome.status)
                if not step_outcome.committed:
                    if step_outcome.terminal or bool(
                        getattr(solver, "stop_requested", False)
                    ):
                        termination_reason = str(
                            getattr(solver, "stop_reason", None)
                            or step_outcome.reason
                            or step_outcome.status
                        )
                        break
                    continue
                steps_executed += 1
                _call_optional(solver, "_record_completed_run_step")
                if callable(control):
                    generation_control_started = True
                    control(GENERATION_START)
                try:
                    generation_plugin_receipt = solver.plugin_manager.begin_lifecycle(
                        "on_generation_start",
                        generation,
                    )
                except PluginLifecycleDispatchError as exc:
                    generation_plugin_receipt = exc.receipt
                    raise
                _call_optional(solver.plugin_manager, "on_step", solver, generation)
                _call_optional(
                    solver.plugin_manager,
                    "on_generation_committed",
                    generation,
                    attempt_payload,
                )
                if callable(control):
                    control(GENERATION_COMMITTED)
                _call_optional(
                    solver,
                    "_runtime_governance_on_generation_end",
                    generation,
                )
                if callback is not None and bool(callback(solver)):
                    termination_reason = "callback"
                    break
                if bool(getattr(solver, "stop_requested", False)):
                    termination_reason = str(
                        getattr(solver, "stop_reason", None) or "user_stop"
                    )
                    break
            except BaseException as exc:
                if not attempt_recorded:
                    _call_optional(solver, "_record_run_step_attempt", "failed")
                    attempt_payload = {
                        "status": "failed",
                        "committed": False,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                raise
            finally:
                cleanup_callbacks: list[tuple[str, Callable[[], None]]] = []
                if generation_plugin_receipt.participants:
                    cleanup_callbacks.append(
                        (
                            "plugin.on_generation_end",
                            lambda: solver.plugin_manager.finish_lifecycle(
                                generation_plugin_receipt,
                                "on_generation_end",
                                generation,
                            ),
                        )
                    )
                if generation_control_started and callable(control):
                    cleanup_callbacks.append(
                        ("controller.generation_end", lambda: control(GENERATION_END))
                    )
                if control_started and callable(control):
                    cleanup_callbacks.append(
                        ("controller.attempt_end", lambda: control(ATTEMPT_END))
                    )
                if attempt_plugin_receipt.participants:
                    cleanup_callbacks.append(
                        (
                            "plugin.on_step_attempt_end",
                            lambda: solver.plugin_manager.finish_lifecycle(
                                attempt_plugin_receipt,
                                "on_step_attempt_end",
                                attempt_number,
                                generation,
                                attempt_payload,
                            ),
                        )
                    )
                _finish_lifecycle_participants(cleanup_callbacks)

        elapsed = max(
            0.0,
            float(time.time() - float(getattr(solver, "start_time", time.time()))),
        )
        total_steps = int(start_step) + int(steps_executed)
        total_attempts = int(resume_attempts_from) + int(step_attempts_executed)
        set_generation = getattr(solver, "set_generation", None)
        if callable(set_generation):
            set_generation(total_steps)
        else:
            solver.generation = total_steps
        result.update(
            {
                "status": (
                    "stopped"
                    if bool(getattr(solver, "stop_requested", False))
                    or termination_reason in {"attempt_limit", "idle_attempt_limit"}
                    else "ok"
                ),
                "termination_reason": termination_reason,
                "generation": int(total_steps),
                "step_attempts": int(total_attempts),
                "step_attempts_executed": int(step_attempts_executed),
                "resume_attempts_from": int(resume_attempts_from),
                "max_step_attempts": int(attempt_limit),
                "last_step_outcome": (
                    None
                    if last_step_outcome is None
                    else last_step_outcome.as_dict()
                ),
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
        _checkpoint_case_runtime(solver)
        run_finish_attempted = True
        finish_callbacks: list[tuple[str, Callable[[], None]]] = []
        if runtime_governance_started:
            finish_callbacks.append(
                (
                    "runtime_governance.on_solver_finish",
                    lambda: _call_optional(
                        solver,
                        "_runtime_governance_on_solver_finish",
                        result,
                    ),
                )
            )
        if run_plugin_receipt.participants:
            finish_callbacks.append(
                (
                    "plugin.on_solver_finish",
                    lambda: solver.plugin_manager.finish_lifecycle(
                        run_plugin_receipt,
                        "on_solver_finish",
                        result,
                    ),
                )
            )
        _finish_lifecycle_participants(finish_callbacks)
        completed_result = result
    except BaseException as exc:
        primary_error = exc
        dispatcher = getattr(solver, "_dispatch_error_once", None)
        failure_result = {
            "status": "failed",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "finalized": False,
        }
        failure_callbacks: list[tuple[str, Callable[[], None]]] = []
        if callable(dispatcher):
            failure_callbacks.append(("plugin.on_error", lambda: dispatcher(exc)))
        elif not bool(getattr(exc, "_nsgablack_error_dispatched", False)):
            pm = getattr(solver, "plugin_manager", None)
            if pm is not None:
                error_context = dict(getattr(solver, "build_context", lambda: {})() or {})
                phase = getattr(exc, "_nsgablack_error_phase", None)
                if phase:
                    error_context["error_phase"] = str(phase)
                error_context.update(dict(getattr(exc, "_nsgablack_error_context", {}) or {}))
                failure_callbacks.append(
                    (
                        "plugin.on_error",
                        lambda: pm.finish_lifecycle(
                            run_plugin_receipt,
                            "on_error",
                            exc,
                            error_context,
                        ),
                    )
                )
        if not run_finish_attempted and run_plugin_receipt.participants:
            run_finish_attempted = True
            failure_callbacks.append(
                (
                    "plugin.on_solver_finish",
                    lambda: solver.plugin_manager.finish_lifecycle(
                        run_plugin_receipt,
                        "on_solver_finish",
                        failure_result,
                    ),
                )
            )
        _finish_lifecycle_participants(failure_callbacks)
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
                try:
                    attach_failure_evidence(
                        primary_error,
                        "nsgablack_teardown",
                        cleanup_evidence,
                    )
                except Exception:
                    pass
                add_note = getattr(primary_error, "add_note", None)
                if callable(add_note):
                    add_note(
                        "Solver teardown also failed: "
                        f"{cleanup_evidence['type']}: {cleanup_evidence['message']}"
                    )
        finally:
            solver.running = False
            setattr(solver, "_runtime_setup_complete", False)
            setattr(solver, "_restore_collection_active", False)
            setattr(solver, "_restore_apply_active", False)
            if primary_error is not None:
                setattr(solver, "_run_plugin_receipt", None)

    if completed_result is None:  # pragma: no cover - guarded by lifecycle flow
        raise RuntimeError("solver lifecycle completed without a result")
    transactional_prepare = getattr(
        solver,
        "prepare_finalization_after_teardown",
        None,
    )
    transactional_freeze = getattr(
        solver,
        "freeze_finalization_after_prepare",
        None,
    )
    transactional_abort = getattr(
        solver,
        "abort_finalization_after_teardown",
        None,
    )
    uses_transactional_finalization = callable(transactional_prepare)
    semantic_finalization_frozen = False
    case_runtime = getattr(solver, "case_runtime", None)
    runtime_finalization_abort = getattr(
        case_runtime,
        "abort_finalization_transaction",
        None,
    )
    try:
        if uses_transactional_finalization:
            if not callable(transactional_freeze):
                raise TypeError(
                    "transactional finalization requires "
                    "freeze_finalization_after_prepare(...)"
                )
            setattr(solver, "_post_teardown_finalization_active", True)
            prepared = transactional_prepare(completed_result)
            if prepared is not None:
                completed_result = prepared
        else:
            post_teardown = getattr(solver, "finalize_after_teardown", None)
            if callable(post_teardown):
                finalized = post_teardown(completed_result)
                if finalized is not None:
                    completed_result = finalized
        if run_plugin_receipt.participants:
            solver.plugin_manager.finish_lifecycle(
                run_plugin_receipt,
                "on_solver_finalization_prepare",
                completed_result,
            )
        if uses_transactional_finalization:
            finalized = transactional_freeze(completed_result)
            if finalized is not None:
                completed_result = finalized
        # Semantic freeze only prepares the result and staged refs.  BlackBase's
        # CaseExecutor seals the shared publication transaction after output
        # serialization, heartbeat shutdown and runtime cleanup succeed.
        setattr(solver, "last_result", completed_result)
        if run_plugin_receipt.participants:
            def notify_finalized(_publications=None) -> None:
                solver.plugin_manager.finish_lifecycle(
                    run_plugin_receipt,
                    "on_solver_finalized",
                    completed_result,
                )

            register_observer = getattr(
                case_runtime,
                "register_finalization_observer",
                None,
            )
            if case_runtime is not None:
                if not callable(register_observer):
                    raise TypeError(
                        "Case runtime must implement "
                        "register_finalization_observer(...)"
                    )
                register_observer(
                    notify_finalized,
                    name="nsgablack.plugin_manager.on_solver_finalized",
                )
            else:
                try:
                    notify_finalized()
                except BaseException as observer_error:
                    evidence = {
                        "observer": "nsgablack.plugin_manager.on_solver_finalized",
                        "error_type": type(observer_error).__name__,
                        "message": str(observer_error),
                    }
                    setattr(solver, "_finalization_observer_failures", (evidence,))
                    logger.error(
                        "Non-veto solver finalization observer failed",
                        exc_info=(
                            type(observer_error),
                            observer_error,
                            observer_error.__traceback__,
                        ),
                    )
        _checkpoint_case_runtime(solver)
        semantic_finalization_frozen = True
    except BaseException as exc:
        if (
            uses_transactional_finalization
            and not semantic_finalization_frozen
            and callable(transactional_abort)
        ):
            try:
                transactional_abort(exc)
            except BaseException as abort_error:
                try:
                    attach_failure_evidence(
                        exc,
                        "finalization_abort",
                        {
                            "error_type": type(abort_error).__name__,
                            "message": str(abort_error),
                        },
                    )
                except Exception:
                    pass
        if not semantic_finalization_frozen and callable(runtime_finalization_abort):
            try:
                runtime_finalization_abort(
                    f"{type(exc).__name__}: {exc}"
                )
            except BaseException as abort_error:
                try:
                    attach_failure_evidence(
                        exc,
                        "case_finalization_abort",
                        {
                            "error_type": type(abort_error).__name__,
                            "message": str(abort_error),
                        },
                    )
                except Exception:
                    pass
        dispatcher = getattr(solver, "_dispatch_error_once", None)
        if callable(dispatcher):
            dispatcher(exc, phase="solver_finalization")
        raise
    finally:
        setattr(solver, "_post_teardown_finalization_active", False)
        setattr(solver, "_run_plugin_receipt", None)
    return completed_result


__all__ = [
    "apply_runtime_control_slot",
    "run_solver_loop",
]
