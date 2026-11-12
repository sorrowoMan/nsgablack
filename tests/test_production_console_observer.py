"""Console reporting projects committed state without hidden model evaluations."""
import importlib
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from blackbase.project import case_import_context
from nsgablack.core.state.incumbent import IncumbentState


PROJECT = Path(__file__).resolve().parents[1] / "examples/cases/production_scheduling"


def plugin():
    with case_import_context(PROJECT, "production_scheduling"):
        cls = importlib.import_module("plugins.runtime_plugins").ConsoleProgressPlugin
    return cls(report_every=1)


class Problem:
    def __init__(self, decode=None):
        self.calls = Counter()
        self.decode = decode

    def evaluate(self, candidate):
        self.calls["evaluate"] += 1
        raise AssertionError("console performed a model evaluation")

    def evaluate_constraints(self, candidate):
        self.calls["evaluate_constraints"] += 1
        raise AssertionError("console recomputed constraints")

    def decode_schedule(self, candidate):
        self.calls["decode_schedule"] += 1
        return np.asarray(candidate).reshape(2, 2) if self.decode is None else self.decode(candidate)


class Solver:
    def __init__(self, incumbent, problem=None):
        self.incumbent = incumbent
        self.problem = Problem() if problem is None else problem
        self.last_step_summary = {"num_candidates": 4}
        self.incumbent_reads = 0
        self.provider_calls = 0
        self.evaluation_provider = SimpleNamespace(evaluate=self._forbidden_evaluate,
                                                   evaluate_batch=self._forbidden_evaluate)

    def get_incumbent(self):
        self.incumbent_reads += 1
        assert self.incumbent_reads == 1, "one report must use one authoritative incumbent"
        return self.incumbent

    def _forbidden_evaluate(self, *args, **kwargs):
        self.provider_calls += 1
        raise AssertionError("console called the control-plane/Provider evaluator")

    evaluate_individual = evaluate_population = _forbidden_evaluate

    @property
    def best_x(self):
        raise AssertionError("console read an independent legacy candidate field")

    @property
    def best_objective(self):
        raise AssertionError("console read an independent legacy score field")

    @property
    def history(self):
        raise AssertionError("console guessed raw feedback from history")

    def get_last_feedback_batch(self):
        raise AssertionError("console guessed raw feedback from a different evaluation")


def report(solver, capsys):
    observer = plugin()
    observer.solver = solver
    observer.on_solver_init(solver)
    observer.on_generation_committed(1, None)
    text = capsys.readouterr().out
    assert solver.incumbent_reads == 1
    assert solver.provider_calls == 0
    assert solver.problem.calls["evaluate"] == solver.problem.calls["evaluate_constraints"] == 0
    return text


def incumbent(**kwargs):
    return IncumbentState(candidate=[1., 2., 3., 4.], objectives=[-9999., 42.],
                          constraint_violation=kwargs.get("violation", .25),
                          score=kwargs.get("score", -7.), candidate_token="evaluated-incumbent")


def test_console_uses_one_incumbent_and_pure_schedule_projection(capsys):
    state = incumbent()
    solver = Solver(state)
    text = report(solver, capsys)
    assert "best_score=-7" in text
    assert "best_total_output=10" in text  # not -selection_objectives[0]
    assert "best_selection_violation=0.25" in text
    assert "best_constraint_violation=" not in text
    assert solver.problem.calls == {"decode_schedule": 1}
    np.testing.assert_array_equal(state.candidate, [1., 2., 3., 4.])


def test_softened_selection_violation_is_not_presented_as_raw_feasibility(capsys):
    solver = Solver(incumbent(violation=0.))
    # The observer has no token/version-bound raw evidence. It must not use
    # objectives, last feedback or history to invent that missing fact.
    text = report(solver, capsys)
    assert "best_selection_violation=0" in text
    assert "best_constraint_violation=" not in text
    assert "raw" not in text and "feasible" not in text


def test_console_without_incumbent_reports_unavailable_metrics(capsys):
    solver = Solver(None)
    text = report(solver, capsys)
    assert "best_score=n/a" in text and "best_total_output=n/a" in text
    assert "best_selection_violation=n/a" in text
    assert not solver.problem.calls


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf, "invalid", [1., 2.], None, True, 1j])
def test_invalid_selection_metrics_are_not_printed_as_measurements(value, capsys):
    state = SimpleNamespace(candidate=np.arange(1., 5.), score=value, constraint_violation=value)
    text = report(Solver(state), capsys)
    assert "best_score=n/a" in text and "best_selection_violation=n/a" in text
    assert "best_total_output=10" in text


@pytest.mark.parametrize("candidate", [[], [[1., 2.]], [np.nan], [np.inf], ["bad"], [1j], None])
def test_invalid_candidate_does_not_reach_schedule_decoder(candidate, capsys):
    solver = Solver(SimpleNamespace(candidate=candidate, score=2., constraint_violation=0.))
    text = report(solver, capsys)
    assert "best_total_output=n/a" in text
    assert "best_score=2" in text and "best_selection_violation=0" in text
    assert not solver.problem.calls


@pytest.mark.parametrize("schedule", [[], [1., 2.], [[np.nan]], [[np.inf]], [[1j]], [["bad"]],
                                       [[np.finfo(float).max, np.finfo(float).max]]])
def test_invalid_schedule_projection_reports_unavailable_total(schedule, capsys):
    text = report(Solver(incumbent(), Problem(decode=lambda _: schedule)), capsys)
    assert "best_total_output=n/a" in text
    assert "best_score=-7" in text and "best_selection_violation=0.25" in text


def test_schedule_shape_error_is_unavailable_without_evaluation_fallback(capsys):
    def fail(_):
        raise ValueError("schedule shape mismatch")
    text = report(Solver(incumbent(), Problem(decode=fail)), capsys)
    assert "best_total_output=n/a" in text
