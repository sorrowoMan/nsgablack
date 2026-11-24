"""Opt-in, per-process profiling for this diagnostic Project only."""
import os


if os.environ.get("NSGABLACK_RUNTIME_PROFILE_DIR"):
    import atexit
    import cProfile
    import gc
    import json
    from pathlib import Path
    import sys
    import time
    import functools
    import threading

    project = Path(__file__).resolve().parents[1]
    run_id = os.environ["NSGABLACK_RUNTIME_COST_RUN_ID"]
    output = Path(os.environ["NSGABLACK_RUNTIME_PROFILE_DIR"]).resolve()
    expected = (project / ".blackbase" / "runs" / run_id / "profiles").resolve()
    if output != expected:
        raise ValueError("runtime profile directory is outside the selected Project run")
    output.mkdir(parents=True, exist_ok=True)
    bootstrap = (time.perf_counter(), time.process_time(), time.thread_time())
    profile = None
    started = None
    saved = False
    gc_started = None
    gc_metrics = {"collections": 0, "wall_seconds": 0.0, "thread_cpu_seconds": 0.0,
                  "collected": 0, "uncollectable": 0}
    scope_metrics = {}
    scope_local = threading.local()
    scope_lock = threading.Lock()

    def timed_scope(label, function):
        @functools.wraps(function)
        def measured(*args, **kwargs):
            stack = getattr(scope_local, "stack", None)
            if stack is None:
                scope_local.stack = stack = []
            entry = [time.perf_counter(), time.thread_time(), 0.0, 0.0]
            stack.append(entry)
            try:
                return function(*args, **kwargs)
            finally:
                wall, cpu = time.perf_counter()-entry[0], time.thread_time()-entry[1]
                stack.pop()
                if stack:
                    stack[-1][2] += wall
                    stack[-1][3] += cpu
                with scope_lock:
                    values = scope_metrics.setdefault(label, dict(calls=0, wall_exclusive=0.0,
                        thread_cpu_exclusive=0.0, wall_inclusive=0.0))
                    values["calls"] += 1
                    values["wall_exclusive"] += wall-entry[2]
                    values["thread_cpu_exclusive"] += cpu-entry[3]
                    values["wall_inclusive"] += wall
        return measured

    def install_timing(case):
        from blackbase.context import snapshot_store as snapshots
        from blackbase.context import redis_codec as codec
        from blackbase.context.snapshot_store import InMemorySnapshotStore
        from blackbase.runtime import RuntimeTransaction
        InMemorySnapshotStore.write = timed_scope("snapshot_write", InMemorySnapshotStore.write)
        RuntimeTransaction.__init__ = timed_scope("rollback_capture", RuntimeTransaction.__init__)
        from blackbase.resources.budget import SQLiteBudgetAuthority
        connect = SQLiteBudgetAuthority._connect
        class BudgetConnectionTiming:
            def __init__(self, connection):
                self.connection = connection
            def __getattr__(self, name):
                return getattr(self.connection, name)
            def __enter__(self):
                self.connection.__enter__()
                return self
            def __exit__(self, *args):
                return timed_scope("budget_context_exit", self.connection.__exit__)(*args)
            def execute(self, *args, **kwargs):
                return timed_scope("budget_sql", self.connection.execute)(*args, **kwargs)
            def commit(self):
                return timed_scope("budget_commit", self.connection.commit)()
            def close(self):
                return timed_scope("budget_close", self.connection.close)()
        @functools.wraps(connect)
        def measured_connect(*args, **kwargs):
            connection = timed_scope("budget_connect", connect)(*args, **kwargs)
            return BudgetConnectionTiming(connection)
        SQLiteBudgetAuthority._connect = measured_connect
        from blackbase.resources._budget_io import _current as budget_scope
        current = budget_scope.get()
        if current is not None:
            for key, connection in tuple(current.connections.items()):
                current.connections[key] = BudgetConnectionTiming(connection)
        for name in ("status", "reserve", "consume", "complete"):
            setattr(SQLiteBudgetAuthority, name, timed_scope("budget_"+name, getattr(SQLiteBudgetAuthority, name)))
        # Measure only outer recursive entries. The recursive implementation
        # still executes unchanged, but re-enters one cheap depth check.
        def outer_scope(label, function):
            if os.environ.get("NSGABLACK_RUNTIME_TIMING_DETAIL") == "coarse":
                return function
            measured = timed_scope(label, function)
            @functools.wraps(function)
            def wrapper(*args, **kwargs):
                if kwargs.get("depth", 0) > 0:
                    return function(*args, **kwargs)
                return measured(*args, **kwargs)
            return wrapper
        preparation_was_standard = snapshots._standard_memory_preparation()
        for module, name, label, recursive in (
            (snapshots, "capture_snapshot_source", "snapshot_capture", False),
            (snapshots, "freeze_snapshot_value", "snapshot_freeze", False),
            (snapshots, "_validate_lossless_snapshot_value", "snapshot_validate", True),
            (snapshots, "_prepare_memory_snapshot", "snapshot_native_other", False),
            (codec, "_to_safe_wire", "snapshot_safe_wire", True),
            (codec.RedisValueCodec, "_dumps_safe_wire", "snapshot_transport_json", False),
            (snapshots, "_canonical_safe_wire_bytes", "snapshot_canonical_json", False),
        ):
            original = getattr(module, name)
            setattr(module, name, (outer_scope if recursive else timed_scope)(label, original))
        # Native preparation has conservative identity guards. Align them only
        # with these known transparent measurement wrappers, never force a
        # different preparation branch. The legacy override remains false.
        snapshots._MEMORY_VALIDATOR = (snapshots._validate_lossless_snapshot_value,
                                       snapshots._validate_lossless_snapshot_value.__code__)
        snapshots._MEMORY_CANONICAL = (snapshots._canonical_safe_wire_bytes,
                                       snapshots._canonical_safe_wire_bytes.__code__)
        if hasattr(snapshots, "_MEMORY_FREEZER"):
            snapshots._MEMORY_FREEZER = (snapshots.freeze_snapshot_value, snapshots.freeze_snapshot_value.__code__)
        snapshots._MEMORY_CODEC_METHODS = tuple((owner, name, getattr(owner, name), getattr(owner, name).__code__)
            for owner, name, _, _ in snapshots._MEMORY_CODEC_METHODS)
        if snapshots._standard_memory_preparation() != preparation_was_standard:
            raise RuntimeError("timing instrumentation changed Memory preparation selection")
        if case is not None:
            from nsgablack.core.state.solution_pool import SolutionPool
            SolutionPool.prepare_publication = timed_scope("pool_prepare", SolutionPool.prepare_publication)
            pipeline = case.solver.representation_pipeline
            pipeline.repair = timed_scope("problem_repair", pipeline.repair)
            problem = case.solver.problem
            problem.evaluate = timed_scope("raw_problem", problem.evaluate)
            problem.evaluate_constraints = timed_scope("raw_constraints", problem.evaluate_constraints)
            solver = case.solver
            for name, label in (
                ("_step_transaction_body", "step_body_other"),
                ("_prepare_snapshot_payload", "authority_payload"),
                ("record_evaluation_event", "event_record"),
                ("write_evaluation_event_snapshot", "event_snapshot"),
                ("_evaluate_population_with_budget_retry", "evaluation_other"),
                ("build_context", "context_build"),
                ("checkpoint_case_runtime", "runtime_control"),
                ("store_solutions", "pool_store_other"),
                ("bind_candidate_batch", "candidate_bind"),
                ("_finalize_evaluation_disposition", "disposition"),
                ("_settle_evaluation_disposition_best_effort", "evidence_settlement"),
                ("commit_snapshot_step_transaction", "authority_commit"),
                ("prepare_solution_pool_retention", "pool_retention"),
                ("stage_evaluation_evidence_archives", "evidence_archive")):
                original = getattr(solver, name, None)
                if callable(original):
                    setattr(solver, name, timed_scope(label, original))
            for name in ("propose", "update"):
                original = getattr(solver.adapter, name)
                setattr(solver.adapter, name, timed_scope("adapter_"+name, original))
            SolutionPool._payload = timed_scope("pool_value_read", SolutionPool._payload)

    def observe_gc(phase, info):
        global gc_started
        if phase == "start":
            gc_started = (time.perf_counter(), time.thread_time())
        elif phase == "stop" and gc_started is not None:
            gc_metrics["collections"] += 1
            gc_metrics["wall_seconds"] += time.perf_counter() - gc_started[0]
            gc_metrics["thread_cpu_seconds"] += time.thread_time() - gc_started[1]
            gc_metrics["collected"] += info.get("collected", 0)
            gc_metrics["uncollectable"] += info.get("uncollectable", 0)
            gc_started = None

    def start_profile(case=None):
        """Called by the diagnostic thin factory after canonical assembly."""
        global profile, started
        if started is not None:
            return
        if os.environ.get("NSGABLACK_RUNTIME_HOTPATH_REFERENCE") == "legacy":
            import hotpath_reference
            from blackbase.context import snapshot_store
            snapshot_store._prepare_memory_snapshot = hotpath_reference.memory_preparation
        if os.environ.get("NSGABLACK_RUNTIME_IO_REFERENCE") == "legacy":
            from blackbase.resources._budget_io import _current
            current = _current.get()
            if current is not None:
                current.close()  # Subsequent operations use transient connections.
            from blackbase.context.snapshot_store import InMemorySnapshotStore, SnapshotStore
            InMemorySnapshotStore.read_verified_content = SnapshotStore.read_verified_content
        if os.environ.get("NSGABLACK_RUNTIME_MEMORY_REFERENCE") == "legacy":
            from blackbase.context import snapshot_store
            snapshot_store._standard_memory_preparation = lambda: False
        # Per-process reference only: exercise the previous implementation's
        # exact persistent codec and discarded-digest paths on the same Case.
        if os.environ.get("NSGABLACK_RUNTIME_UNIT_REFERENCE") == "legacy":
            from nsgablack.units.contracts import UnitBinding
            from nsgablack.units import features
            UnitBinding.snapshot_step = UnitBinding.dump
            UnitBinding.restore_step = UnitBinding.restore
            def legacy_readonly(value):
                return features._snapshot(value)[1]
            features._detached_readonly = legacy_readonly
        started = (time.perf_counter(), time.process_time(), time.thread_time())
        gc.callbacks.append(observe_gc)
        # Native elapsed clock avoids a Python timer call on every event.
        from multiprocessing.util import Finalize
        Finalize(None, save, exitpriority=100)
        if os.environ.get("NSGABLACK_RUNTIME_TIMING_ONLY") == "1":
            install_timing(case)
        else:
            profile = cProfile.Profile()
            profile.enable()

    def save():
        global saved
        if started is None or saved:
            return
        if profile is not None:
            profile.disable()
        pid = os.getpid()
        record = {"pid": pid, "parent_pid": os.getppid(), "entry": Path(sys.argv[0]).name,
                  "timer": "cProfile.default_elapsed" if profile is not None else "timing_scopes",
                  "coverage": "after canonical Case assembly; timing scopes use nested exclusive clocks",
                  "pre_profile_wall_seconds": started[0] - bootstrap[0],
                  "pre_profile_process_cpu_seconds": started[1] - bootstrap[1],
                  "wall_seconds": time.perf_counter() - started[0],
                  "process_cpu_seconds": time.process_time() - started[1],
                  "main_thread_cpu_seconds": time.thread_time() - started[2]}
        gc.callbacks.remove(observe_gc)
        record["gc"] = dict(gc_metrics)
        record["scopes"] = dict(scope_metrics)
        target = output / f"process-{pid}"
        if profile is not None:
            profile.dump_stats(str(target.with_suffix(".prof")))
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target.with_suffix(".json"))
        saved = True

    atexit.register(save)
