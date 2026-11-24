"""Controller stop causes must survive arbitration and the run result."""
from nsgablack.core.control_plane import BudgetController, ControlArbiter
from tests.test_runtime_closure_regressions import _CountingSolver, _Problem


def test_evaluation_budget_reports_its_actual_cause():
    solver = _CountingSolver(_Problem())
    solver.register_controller(BudgetController(max_evaluations=1))
    result = solver.run(max_steps=5)
    assert result["termination_reason"] == "evaluation_budget_exhausted"
    assert result["evaluation_count"] == 1


def test_a_stricter_budget_stop_is_not_hidden_by_an_unexhausted_budget():
    solver = _CountingSolver(_Problem())
    decisions = [BudgetController(max_evaluations=n, name=str(n)).propose(
        solver, "generation_end", {"evaluation_count": 1}) for n in (1, 5)]
    resolved = ControlArbiter().resolve(decisions)["budget"]
    assert resolved.payload["stop"] == 1
    assert resolved.reason == "evaluation_budget_exhausted"


def test_generation_budget_is_distinct_from_evaluation_budget():
    solver = _CountingSolver(_Problem())
    solver.register_controller(BudgetController(max_generations=1))
    assert solver.run(max_steps=5)["termination_reason"] == "generation_budget_exhausted"


def test_manual_stop_keeps_its_own_meaning():
    class Manual(_CountingSolver):
        def step(self):
            outcome = super().step()
            self.request_stop("user_stop")
            return outcome
    assert Manual(_Problem()).run(max_steps=5)["termination_reason"] == "user_stop"
