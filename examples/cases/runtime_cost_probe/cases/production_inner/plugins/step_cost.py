"""Read profiler counters at attempt boundaries without changing search state."""
import json
import os
from pathlib import Path
import sys
import time
from nsgablack.plugins.base import Plugin


def counters():
    profile = getattr(sys.modules.get("sitecustomize"), "profile", None)
    if profile is None:
        return {}
    result = {}
    for entry in profile.getstats():
        code = entry.code
        key = (code.co_filename, code.co_firstlineno, code.co_name) if hasattr(code, "co_filename") else ("~", 0, str(code))
        result[key] = (entry.callcount, entry.inlinetime)
    return result


class StepCostObserver(Plugin):
    def __init__(self):
        super().__init__("diagnostic_step_cost")
        self.rows = []

    def on_step_attempt_start(self, attempt, logical_step):
        self.before = counters()
        self.gc_before = dict(getattr(sys.modules.get("sitecustomize"), "gc_metrics", {}))
        self.scope_before = {key: dict(value) for key, value in
            getattr(sys.modules.get("sitecustomize"), "scope_metrics", {}).items()}
        self.started = (time.perf_counter(), time.thread_time(), self.solver.evaluation_count)

    def on_step_attempt_end(self, attempt, logical_step, outcome):
        finished = (time.perf_counter(), time.thread_time(), self.solver.evaluation_count)
        gc_after = getattr(sys.modules.get("sitecustomize"), "gc_metrics", {})
        scopes_after = getattr(sys.modules.get("sitecustomize"), "scope_metrics", {})
        delta = []
        for key, (calls, own) in counters().items():
            old_calls, old_own = self.before.get(key, (0, 0.0))
            if calls != old_calls or own != old_own:
                delta.append(dict(file=key[0], line=key[1], function=key[2], calls=calls-old_calls,
                                  self_elapsed_seconds=own-old_own))
        self.rows.append(dict(attempt=attempt, logical_step=logical_step,
            outcome=dict(outcome) if isinstance(outcome, dict) else str(outcome),
            wall_seconds=finished[0]-self.started[0], thread_cpu_seconds=finished[1]-self.started[1],
            evaluations=finished[2]-self.started[2], functions=delta,
            gc={key: value-self.gc_before.get(key, 0) for key, value in gc_after.items()},
            scopes={name: {key: value-self.scope_before.get(name, {}).get(key, 0)
                           for key, value in values.items()} for name, values in scopes_after.items()}))

    def on_solver_finish(self, solver):
        folder = Path(os.environ["NSGABLACK_RUNTIME_COST_RUN_ROOT"])
        target = folder / f"steps-{os.getpid()}.json"
        target.write_text(json.dumps(dict(rows=self.rows, note="Self elapsed counters only; excludes build and finalization; instrumentation has cost"), indent=2)+"\n", encoding="utf-8")
