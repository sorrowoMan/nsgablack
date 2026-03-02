from __future__ import annotations


def test_set_plugin_strict_helper():
    from nsgablack.core.blank_solver import SolverBase
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.utils.suites import set_plugin_strict

    class _P(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="p", dimension=1, bounds={"x0": (-1.0, 1.0)})

        def evaluate(self, x):
            return float(x[0] ** 2)

    solver = SolverBase(problem=_P())
    assert bool(getattr(solver.plugin_manager, "strict", False)) is False
    set_plugin_strict(solver, True)
    assert bool(getattr(solver.plugin_manager, "strict", False)) is True


def test_set_parallel_thread_bias_isolation_helper():
    from nsgablack.core.blank_solver import SolverBase
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.utils.parallel import with_parallel_evaluation
    from nsgablack.utils.suites import set_parallel_thread_bias_isolation

    class _P(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="p", dimension=1, bounds={"x0": (-1.0, 1.0)})

        def evaluate(self, x):
            return float(x[0] ** 2)

    ParallelBlank = with_parallel_evaluation(SolverBase)
    solver = ParallelBlank(problem=_P(), enable_parallel=True, parallel_backend="thread")

    set_parallel_thread_bias_isolation(solver, "disable_cache")
    assert getattr(solver, "parallel_thread_bias_isolation", None) == "disable_cache"
    assert solver._parallel_cfg.get("thread_bias_isolation") == "disable_cache"
