"""内部真实 Solver 使用父 Case 的同一控制检查，不接管其发布事务。"""
from dataclasses import replace
from functools import wraps

import numpy as np
import pytest

from blackbase.project import CaseRunRequest, CaseRuntimeContext, ExecutionControl
from blackbase.resources import CancellationHeartbeat, CancellationRef, CancellationRequested, CancellationToken
from benchmarks.transparency_core import build_pair_solver, run_pair
from benchmarks.transparency_population import specs as population_specs
from benchmarks.transparency_structured import specs as structured_specs
from nsgablack.core import BlackBoxProblem


def test_real_third_problem_call_cancellation_stops_the_remaining_batch(tmp_path):
    ref = CancellationRef(backend="sqlite", path=str(tmp_path / "control.sqlite"), namespace="transparency-parent-control")
    token = CancellationToken(ref)
    heartbeat = CancellationHeartbeat(token)
    runtime = CaseRuntimeContext(request=CaseRunRequest(project_name="control-test", stage_name="batch", case_name="matrix",
        control=ExecutionControl(cancellation=ref)), cancellation_tokens=(token,), invoker=None, stage_scheduler=None)

    class Problem(BlackBoxProblem):
        def __init__(self):
            super().__init__(dimension=8, objectives=["min", "min"], bounds=[(0., 1.)] * 8)
            self.calls = 0

        def evaluate(self, candidate):
            self.calls += 1
            x = np.asarray(candidate)
            if self.calls == 3:
                runtime.cancel("cancel during third real Problem call")
            return np.asarray([x @ x, (1. - x) @ (1. - x)])

    try:
        spec = replace(population_specs(population_size=10, steps=2)[0], make_problem=Problem)
        solver, meter, trace, _ = build_pair_solver(spec, 11, runtime_checkpoint=runtime.checkpoint)
        assert solver.case_runtime is None
        assert token._runtime_state is heartbeat._runtime_state
        with pytest.raises(CancellationRequested, match="third real Problem"):
            solver.run(max_steps=2)
        assert solver.problem.calls == len(meter.records) == solver.evaluation_count == 3
        assert trace.trace == []
    finally:
        heartbeat.close()
        token.retire()


def test_parent_checkpoint_is_connected_to_full_prefix_and_resumed_solver(tmp_path):
    spec = next(spec for spec in structured_specs() if spec.name == "fixed_candidate")
    original_factory = spec.make_problem
    factories, active, observed = [], [None], set()

    def problem_factory():
        problem = original_factory()
        factories.append(problem)
        label = len(factories)
        original = problem.evaluate
        @wraps(original)
        def evaluate(candidate):
            active[0] = label
            return original(candidate)
        problem.evaluate = evaluate
        return problem

    def checkpoint():
        observed.add(active[0])

    result = run_pair(replace(spec, make_problem=problem_factory), seed=11, recovery=True,
                      work_dir=tmp_path, runtime_checkpoint=checkpoint)
    assert result["semantics"]["status"] == result["recovery"]["status"] == "passed", result
    assert len(factories) == 4  # bare reference, full run, checkpoint prefix, resumed run
    assert {2, 3, 4}.issubset(observed)
    assert result["metadata"]["parent_case_checkpoint_connected"] is True
