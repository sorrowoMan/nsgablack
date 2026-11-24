"""真实 Solver.run 与独立参考的公共配对执行器。

由标准透明性 Project/Case 调用；此处没有另一套 setup/step 控制循环。
开销数字是小型诊断值，包含观察/验证成本，不能代表生产吞吐量。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping
from functools import wraps
from pathlib import Path
import tempfile
import time
import traceback
from typing import Callable

import numpy as np


@dataclass(frozen=True)
class PairSpec:
    name: str
    make_problem: Callable
    make_adapter: Callable
    make_pipeline: Callable | None
    reference: Callable
    project: Callable
    steps: int = 6
    population_size: int | None = None
    metric_problem: str | None = None
    metadata: dict = field(default_factory=dict)


def json_value(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(v) for v in value]
    return value


def compare(left, right, path="root"):
    """Return the first concrete mismatch; dictionary ordering is immaterial."""
    if isinstance(left, Mapping) or isinstance(right, Mapping):
        if not isinstance(left, Mapping) or not isinstance(right, Mapping):
            return f"{path}: mapping/value type differs"
        if left.keys() != right.keys():
            return f"{path}: keys differ: {sorted(left.keys())} != {sorted(right.keys())}"
        for key in left:
            issue = compare(left[key], right[key], f"{path}.{key}")
            if issue:
                return issue
        return None
    if left is None or right is None:
        return None if left is right else f"{path}: {left!r} != {right!r}"
    if isinstance(left, (str, bool)) or isinstance(right, (str, bool)):
        return None if type(left) is type(right) and left == right else f"{path}: {left!r} != {right!r}"
    if isinstance(left, (int, np.integer)) and isinstance(right, (int, np.integer)):
        return None if left == right else f"{path}: {left!r} != {right!r}"
    if isinstance(left, (list, tuple)) or isinstance(right, (list, tuple)):
        if not isinstance(left, (list, tuple)) or not isinstance(right, (list, tuple)) or len(left) != len(right):
            return f"{path}: sequence lengths/types differ"
        for index, (a, b) in enumerate(zip(left, right)):
            issue = compare(a, b, f"{path}[{index}]")
            if issue:
                return issue
        return None
    try:
        if bool(np.isclose(left, right, rtol=1e-10, atol=1e-10, equal_nan=False)):
            return None
    except (TypeError, ValueError):
        pass
    return f"{path}: {left!r} != {right!r}"


def _rss():
    try:
        import psutil
        return int(psutil.Process().memory_info().rss)
    except ImportError:
        return None


def _io():
    try:
        import psutil
    except ImportError:
        return None
    try:
        return dict(psutil.Process().io_counters()._asdict())
    except (AttributeError, OSError, psutil.Error):
        return None


class ProblemMeter:
    """Observe the actual Problem calls; never count framework event rows instead."""
    def __init__(self, problem, *, record_calls=True):
        from blackbase.types import Feedback
        self.problem, self.records = problem, []
        self.record_calls, self.call_count = bool(record_calls), 0
        self.wall_s = self.cpu_s = 0.
        self._feedback_type = Feedback
        original = problem.evaluate
        original_constraints = getattr(problem, "evaluate_constraints", None)

        @wraps(original)
        def evaluated(candidate, *args, **kwargs):
            wall, cpu = time.perf_counter(), time.process_time()
            try:
                result = original(candidate, *args, **kwargs)
            finally:
                self.wall_s += time.perf_counter() - wall
                self.cpu_s += time.process_time() - cpu
            self.call_count += 1
            if not self.record_calls:
                return result
            if isinstance(result, Feedback):
                f = result.objectives
                violation = float(np.maximum(np.asarray(result.constraints, dtype=float), 0.).sum())
            else:
                f, violation = result, None
            self.records.append({"x": np.asarray(candidate, dtype=float).reshape(-1).tolist(),
                "f": np.asarray(f, dtype=float).reshape(-1).tolist(), "v": violation})
            return result

        @wraps(original_constraints)
        def constrained(candidate, *args, **kwargs):
            wall, cpu = time.perf_counter(), time.process_time()
            try:
                result = original_constraints(candidate, *args, **kwargs)
            finally:
                self.wall_s += time.perf_counter() - wall
                self.cpu_s += time.process_time() - cpu
            if not self.record_calls:
                return result
            x = np.asarray(candidate, dtype=float).reshape(-1).tolist()
            for row in reversed(self.records):
                if row["x"] == x:
                    row["v"] = float(np.maximum(np.asarray(result, dtype=float), 0.).sum())
                    break
            return result

        problem.evaluate = evaluated
        if callable(original_constraints):
            problem.evaluate_constraints = constrained

    def evaluate(self, candidate):
        """The independent reference receives the same Problem, via one F call."""
        raw = self.problem.evaluate(candidate)
        if isinstance(raw, self._feedback_type):
            f = raw.objectives
            v = float(np.maximum(np.asarray(raw.constraints, dtype=float), 0.).sum())
            if self.record_calls:
                self.records[-1]["v"] = v
        else:
            f = raw
            fn = getattr(self.problem, "evaluate_constraints", None)
            constraints = fn(candidate) if callable(fn) else ()
            v = float(np.maximum(np.asarray(constraints, dtype=float), 0.).sum())
            if self.record_calls:
                self.records[-1]["v"] = v
        return np.asarray(f, dtype=float).reshape(-1), v

    def summary(self):
        return {"calls": self.call_count, "wall_s": self.wall_s, "cpu_s": self.cpu_s,
                "gradient_calls": getattr(self.problem, "gradient_calls", None)}


def build_pair_solver(spec, seed, *, resource_context=None, checkpoint_dir=None, runtime_checkpoint=None,
                      capture_trace=True, record_calls=True):
    """Public assembly helper for the benchmark Case and recovery validation."""
    from nsgablack.core import ComposableSolver
    from nsgablack.plugins.base import Plugin
    from blackbase.resources import ResourceContext

    class Trace(Plugin):
        def __init__(self):
            super().__init__("transparency_trace")
            self.trace, self.rss_samples = [], []
            self.attempt_timings = []
            self._attempt_clock = None
            self.commits = 0
            self.observation_wall_s = self.observation_cpu_s = 0.0

        def on_step_attempt_start(self, attempt, logical_step):
            self._attempt_clock = (time.perf_counter(), time.process_time(), meter.wall_s, meter.cpu_s,
                                   meter.call_count)
            repair = getattr(self, "repair_meter", None)
            self._repair_clock = (getattr(repair, "wall_s", 0.), getattr(repair, "cpu_s", 0.))

        def on_step_attempt_end(self, attempt, logical_step, outcome):
            if self._attempt_clock is None:
                raise RuntimeError("attempt end has no matching timing start")
            wall, cpu, problem_wall, problem_cpu, calls = self._attempt_clock
            self.attempt_timings.append({"attempt": int(attempt), "logical_step": int(logical_step),
                "status": str(outcome.get("status", "unknown")),
                "wall_s": time.perf_counter() - wall, "cpu_s": time.process_time() - cpu,
                "problem_wall_s": meter.wall_s - problem_wall, "problem_cpu_s": meter.cpu_s - problem_cpu,
                "evaluation_calls": meter.call_count - calls,
                "repair_wall_s": getattr(getattr(self, "repair_meter", None), "wall_s", 0.) - self._repair_clock[0],
                "repair_cpu_s": getattr(getattr(self, "repair_meter", None), "cpu_s", 0.) - self._repair_clock[1]})
            self._attempt_clock = None

        def on_generation_committed(self, generation, outcome):
            self.commits += 1
            if capture_trace:
                wall, cpu = time.perf_counter(), time.process_time()
                self.trace.append({"state": json_value(spec.project(self.solver))})
                self.rss_samples.append(_rss())
                self.observation_wall_s += time.perf_counter() - wall
                self.observation_cpu_s += time.process_time() - cpu

    if runtime_checkpoint is not None and not callable(runtime_checkpoint):
        raise TypeError("runtime_checkpoint must be callable")

    class ControlledPairSolver(ComposableSolver):
        def checkpoint_case_runtime(self):
            runtime_checkpoint()

    problem = spec.make_problem()
    meter = ProblemMeter(problem, record_calls=record_calls)
    grant = resource_context if resource_context is not None else ResourceContext(
        namespace="transparency_local_diagnostic", grant={"threads": 1, "workers": 1})
    solver_type = ComposableSolver if runtime_checkpoint is None else ControlledPairSolver
    solver = solver_type(problem, adapter=spec.make_adapter(int(seed)),
        representation_pipeline=None if spec.make_pipeline is None else spec.make_pipeline(int(seed)),
        resource_context=grant, plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(int(seed))
    solver.enable_progress_log = False
    if spec.population_size is not None:
        solver.pop_size = int(spec.population_size)
    trace = Trace()
    solver.add_plugin(trace)
    checkpoint = None
    if checkpoint_dir is not None:
        from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
        directory = str(Path(checkpoint_dir).resolve())
        checkpoint = CheckpointResumePlugin(config=CheckpointResumeConfig(checkpoint_dir=directory,
            save_every=0, save_on_finish=False, strict=False, trusted_roots=(directory,)))
        solver.add_plugin(checkpoint)
    return solver, meter, trace, checkpoint


def _timed(fn, *, samples=()):
    start_rss, start_io = _rss(), _io()
    start_wall, start_cpu = time.perf_counter(), time.process_time()
    value = fn()
    cpu, wall, end_rss = time.process_time() - start_cpu, time.perf_counter() - start_wall, _rss()
    end_io = _io()
    observed = [v for v in (start_rss, *samples, end_rss) if v is not None]
    io = ({"status": "unsupported", "reason": "psutil process I/O counters unavailable"}
          if start_io is None or end_io is None else
          {"status": "measured", "delta": {key: end_io[key] - start_io[key] for key in start_io},
           "scope": "same-process run interval; includes observation and evidence I/O"})
    return value, {"wall_s": wall, "cpu_s": cpu, "rss_start_bytes": start_rss, "rss_end_bytes": end_rss,
        "peak_observed_rss_bytes": max(observed) if observed else None,
        "rss_delta_bytes": None if start_rss is None or end_rss is None else end_rss - start_rss,
        "io": io}


def _failure(exc):
    return {"status": "failed", "error_type": type(exc).__name__, "error": str(exc),
            "traceback": traceback.format_exc()}


def _checks(checks):
    failures = {name: issue for name, issue in checks.items() if issue}
    return {"status": "failed" if failures else "passed", "checks": {k: v is None for k, v in checks.items()},
            "mismatches": failures}


def _timing_summary(rows):
    if not rows:
        return {"status": "unsupported", "reason": "no normal committed iteration"}
    return {"status": "measured", "count": len(rows), "rows": rows,
        **{f"{key}_{aggregation}": float(function([r[key] for r in rows]))
           for key in ("wall_s", "cpu_s") for aggregation, function in
           (("sum", np.sum), ("mean", np.mean), ("median", np.median))}}


def _iteration_overhead(bare, attempt_timings):
    framework = [row for row in attempt_timings if row["status"] == "committed"]
    reference = bare.get("iteration_timings")
    supported = isinstance(reference, list) and len(reference) == len(framework)
    unsupported = {"status": "unsupported", "reason": "reference did not provide aligned per-iteration timing"}
    bootstrap = {"status": "measured" if supported else "unsupported",
        "framework": framework[0] if framework else None,
        "reference": reference[0] if supported and reference else unsupported}
    normal = {"status": "measured" if supported else "unsupported",
        "framework": _timing_summary(framework[1:]),
        "reference": _timing_summary(reference[1:]) if supported else unsupported,
        "scope": "commits after bootstrap; attempt lifecycle includes evidence, transaction and trace observation"}
    if supported:
        normal["paired"] = [{"commit": index + 2, "wall_difference_s": a["wall_s"] - b["wall_s"],
            "cpu_difference_s": a["cpu_s"] - b["cpu_s"],
            "wall_ratio": a["wall_s"] / b["wall_s"] if b["wall_s"] else None}
            for index, (a, b) in enumerate(zip(framework[1:], reference[1:]))]
    return {"bootstrap": bootstrap, "normal_iterations": normal, "physical_attempt_timings": attempt_timings}


def run_pair(spec, seed=11, recovery=True, resource_context=None, work_dir=None, runtime_checkpoint=None):
    """Compare independent reference with complete run, then real checkpoint resume."""
    output = {"name": spec.name, "seed": int(seed), "steps": spec.steps, "metadata": json_value(spec.metadata)}
    output["metadata"]["parent_case_checkpoint_connected"] = runtime_checkpoint is not None
    output["metadata"]["solver_evidence_scope"] = "Solver-local stores; aggregate report is published by the enclosing Case"
    try:
        bare_meter = ProblemMeter(spec.make_problem())
        bare, bare_time = _timed(lambda: spec.reference(int(seed), int(spec.steps), bare_meter.evaluate))
        bare = json_value(bare)
    except Exception as exc:
        output.update(semantics=_failure(exc), quality={"status": "unsupported", "reason": "reference failed"},
            overhead={"status": "failed", "reason": "reference failed"},
            recovery={"status": "unsupported", "reason": "reference failed"})
        return output
    try:
        started = time.perf_counter()
        solver, meter, trace, _ = build_pair_solver(spec, seed, resource_context=resource_context,
            runtime_checkpoint=runtime_checkpoint)
        assembly_wall = time.perf_counter() - started
        result, framework_time = _timed(lambda: solver.run(max_steps=spec.steps), samples=trace.rss_samples)
        observed = [x for x in (*trace.rss_samples, framework_time["peak_observed_rss_bytes"]) if x is not None]
        framework_time["peak_observed_rss_bytes"] = max(observed) if observed else None
        state = json_value(spec.project(solver))
        bare_trace = [{"state": row["state"]} for row in bare["trace"]]
        checks = {"final_state": compare(bare["state"], state),
            "committed_trace": compare(bare_trace, trace.trace),
            "evaluation_sequence": compare(bare_meter.records, meter.records),
            "evaluation_count": compare(len(bare_meter.records), int(solver.evaluation_count)),
            "logical_steps": compare(spec.steps, len(trace.trace))}
        output["semantics"] = {**_checks(checks), "reference_evaluations": len(bare_meter.records),
            "framework_evaluations": int(solver.evaluation_count), "reference_state": bare["state"],
            "framework_state": state, "reference_trace": bare_trace, "framework_trace": trace.trace,
            "reference_calls": bare_meter.records, "framework_calls": meter.records,
            "framework_result_status": result.get("status") if isinstance(result, dict) else None}
        output["overhead"] = {"status": "measured", "interpretation": "diagnostic_small_run_with_trace_and_evidence",
            "framework": {**framework_time, "assembly_wall_s": assembly_wall, "problem": meter.summary()},
            "reference": {**bare_time, "problem": bare_meter.summary()},
            "wall_difference_s": framework_time["wall_s"] - bare_time["wall_s"],
            "cpu_difference_s": framework_time["cpu_s"] - bare_time["cpu_s"],
            "wall_ratio": framework_time["wall_s"] / bare_time["wall_s"] if bare_time["wall_s"] else None,
            **_iteration_overhead(bare, trace.attempt_timings),
            "rss_sampling": "process RSS at run boundaries and each framework commit; observed maximum, not isolated allocation peak",
            "timing_scope": "framework assembly separate; complete run includes lifecycle, evidence and trace; reference includes kernel construction"}
    except Exception as exc:
        output.update(semantics=_failure(exc), quality={"status": "unsupported", "reason": "framework run failed"},
            overhead={"status": "failed", "reference": {**bare_time, "problem": bare_meter.summary()}},
            recovery={"status": "unsupported", "reason": "framework run failed"})
        return output
    try:
        from benchmarks.transparency_metrics import quality
        output["quality"] = quality(spec, bare, state, bare_meter.records, meter.records)
    except ImportError as exc:
        output["quality"] = {"status": "unsupported", "reason": "official metric module or dependency unavailable",
                             "error": str(exc)}
    except Exception as exc:
        output["quality"] = _failure(exc)
    if not recovery:
        output["recovery"] = {"status": "unsupported", "reason": "not requested"}
        return output
    try:
        if work_dir is None:
            scratch = Path(__file__).resolve().parents[1] / "runs" / "evidence" / "transparency_checkpoints"
            scratch.mkdir(parents=True, exist_ok=True)
            directory = Path(tempfile.mkdtemp(prefix="pair_", dir=scratch))
        else:
            directory = Path(work_dir)
        checkpoint_dir = directory / spec.name / f"seed_{int(seed)}" / "checkpoints"
        split = max(1, int(spec.steps) // 2)
        prefix, prefix_meter, prefix_trace, writer = build_pair_solver(spec, seed,
            resource_context=resource_context, checkpoint_dir=checkpoint_dir, runtime_checkpoint=runtime_checkpoint)
        prefix.run(max_steps=split)
        path = writer.save_checkpoint(reason="transparency_committed_prefix")
        if path is None:
            raise RuntimeError("checkpoint writer returned no file")
        resumed, resumed_meter, resumed_trace, reader = build_pair_solver(spec, seed,
            resource_context=resource_context, checkpoint_dir=checkpoint_dir, runtime_checkpoint=runtime_checkpoint)
        if not reader.resume(str(path)):
            raise RuntimeError("checkpoint resume was not accepted")
        resumed.run(max_steps=spec.steps)
        restored_state = json_value(spec.project(resumed))
        checks = {"prefix_trace": compare(trace.trace[:split], prefix_trace.trace),
            "resumed_final_state": compare(state, restored_state),
            "suffix_trace": compare(trace.trace[split:], resumed_trace.trace),
            "evaluation_sequence": compare(meter.records, prefix_meter.records + resumed_meter.records),
            "evaluation_count": compare(int(solver.evaluation_count), int(resumed.evaluation_count))}
        output["recovery"] = {**_checks(checks), "checkpoint_path": str(path), "prefix_steps": split,
            "resumed_commits": len(resumed_trace.trace), "resumed_evaluation_calls": len(resumed_meter.records),
            "resume_audit": json_value(reader._last_resume_audit)}
    except Exception as exc:
        output["recovery"] = _failure(exc)
    return json_value(output)


__all__ = ["PairSpec", "ProblemMeter", "build_pair_solver", "compare", "json_value", "run_pair"]
