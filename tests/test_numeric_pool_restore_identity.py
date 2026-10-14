"""Restored working candidates cannot borrow a different pool receipt."""
import copy
from dataclasses import replace

import numpy as np
import pytest

from nsgablack.plugins import CheckpointResumePlugin
from tests.test_pool_numeric_refiners import KINDS, assembled


def evaluated_center(kind):
    solver, adapter, task = assembled(kind, mode="initialize")
    if kind == "gradient":
        # The skipped transition keeps current_x evaluated, as opposed to the
        # ordinary optimizer's deliberately unassessed successor parameters.
        assert adapter.cfg.skip_infeasible
        original = solver.problem.evaluate
        solver.problem.evaluate = lambda candidate: replace(original(candidate),
            info={"constraint_violation": 1.})
    assert solver.step().committed
    assert adapter._pool_results.current is not None
    if kind == "gradient":
        assert not adapter._next_is_proposal
    return solver, adapter, task


def corrupt_working_candidate(adapter, kind):
    state = copy.deepcopy(adapter.get_state())
    unit = adapter.unit_binding.restore(state["algorithm_unit"])
    field = {"gaussian": "best", "mas": "center", "finite_difference": "current",
             "gradient": "current"}[kind]
    setattr(unit, field, np.array(getattr(unit, field), copy=True) + 1.)
    state["algorithm_unit"] = adapter.unit_binding.dump(unit)
    adapter.set_state(state)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("entry", ["roots", "results", "step"])
def test_changed_restored_unit_rejects_old_receipt_before_evaluation(kind, entry):
    solver, adapter, _ = evaluated_center(kind)
    refs = adapter.get_pool_refinement_results(solver)
    assert refs
    corrupt_working_candidate(adapter, kind)
    calls, cost = list(solver.problem.calls), solver.evaluation_count
    with pytest.raises(ValueError, match="candidate values"):
        if entry == "roots":
            adapter.get_solution_pool_roots(solver)
        elif entry == "results":
            adapter.get_pool_refinement_results(solver)
        else:
            solver.step()
    assert solver.problem.calls == calls
    assert solver.evaluation_count == cost
    assert solver.solution_pool.read(refs).numeric_matrix[0, 0] == 8.


@pytest.mark.parametrize("kind", KINDS)
def test_unmodified_evaluated_candidate_roundtrips_and_can_be_used(kind):
    solver, adapter, _ = evaluated_center(kind)
    refs = adapter.get_pool_refinement_results(solver)
    adapter.set_state(copy.deepcopy(adapter.get_state()))
    assert adapter.get_pool_refinement_results(solver) == refs
    assert set(refs).issubset(set(adapter.get_solution_pool_roots(solver)))
    assert solver.step().committed


@pytest.mark.parametrize("kind", KINDS)
def test_missing_restored_evaluated_candidate_cannot_reinitialize(kind):
    solver, adapter, _ = evaluated_center(kind)
    state = copy.deepcopy(adapter.get_state())
    unit = adapter.unit_binding.restore(state["algorithm_unit"])
    field = {"gaussian": "best", "mas": "center", "finite_difference": "current",
             "gradient": "current"}[kind]
    setattr(unit, field, None)
    state["algorithm_unit"] = adapter.unit_binding.dump(unit)
    adapter.set_state(state)
    calls, cost = list(solver.problem.calls), solver.evaluation_count
    with pytest.raises(ValueError, match="requires its"):
        solver.step()
    assert solver.problem.calls == calls
    assert solver.evaluation_count == cost


@pytest.mark.parametrize("kind", ["gaussian", "finite_difference"])
def test_restored_unit_score_must_agree_with_selected_receipt(kind):
    solver, adapter, _ = evaluated_center(kind)
    field = "best_score" if kind == "gaussian" else "current_score"
    setattr(adapter, field, getattr(adapter, field) + 1.)
    adapter.set_state(copy.deepcopy(adapter.get_state()))
    calls = list(solver.problem.calls)
    with pytest.raises(ValueError, match="score differs"):
        solver.step()
    assert solver.problem.calls == calls


@pytest.mark.parametrize("kind", ["finite_difference", "gradient"])
def test_pending_successor_checkpoint_does_not_require_predecessor_identity(kind):
    source, before, _ = assembled(kind, steps=5)
    assert source.step().committed
    if kind == "finite_difference":
        assert source.step().committed
        successor = before._trial_values.copy()
        assert not np.array_equal(successor, before.current_x)
    else:
        assert before._next_is_proposal
        successor = before.current_x.copy()
        predecessor = source.solution_pool.read((before._pool_results.current.ref,)).numeric_matrix[0]
        assert not np.array_equal(successor, predecessor)
    refs = before.get_pool_refinement_results(source)
    target, after, _ = assembled(kind, steps=5, setup=False)
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(source)
    reader.attach(target)
    payload = writer._build_payload(solver=source, reason="pending-numeric-successor")
    target.queue_restore_envelope(lambda: reader._restore_payload(solver=target, payload=payload))
    target.setup()
    target._apply_pending_restore_envelopes()
    assert target.problem.calls == []
    assert after.get_pool_refinement_results(target) == refs
    assert set(refs).issubset(set(after.get_solution_pool_roots(target)))
    assert target.step().committed
    assert target.problem.calls == pytest.approx(successor.tolist())


@pytest.mark.parametrize("entry", ["roots", "results", "step"])
def test_mas_restored_training_candidates_must_match_their_retained_versions(entry):
    solver, adapter, _ = assembled("mas", mode="initialize")
    adapter.cfg.enable_surrogate = True
    # Avoid fitting in this test; the history identity contract is independent
    # of optional model training and prediction.
    adapter.cfg.surrogate_min_train_samples = 100
    assert solver.step().committed
    saved = copy.deepcopy(adapter.get_state())
    saved["history_x"][0][0] += 1.
    unit = adapter.unit_binding.restore(saved["algorithm_unit"])
    unit.history_x[0][0] += 1.
    saved["algorithm_unit"] = adapter.unit_binding.dump(unit)
    adapter.set_state(saved)
    calls = list(solver.problem.calls)
    with pytest.raises(ValueError, match="training candidates"):
        if entry == "roots":
            adapter.get_solution_pool_roots(solver)
        elif entry == "results":
            adapter.get_pool_refinement_results(solver)
        else:
            solver.step()
    assert solver.problem.calls == calls


def test_gradient_cannot_restore_successor_as_if_it_were_already_evaluated():
    solver, adapter, _ = assembled("gradient", mode="initialize")
    assert solver.step().committed
    state = copy.deepcopy(adapter.get_state())
    assert state["next_is_proposal"]
    state["next_is_proposal"] = False
    adapter.set_state(state)
    with pytest.raises(ValueError, match="candidate values"):
        solver.step()
    assert solver.problem.calls == [8.]


@pytest.mark.parametrize("field", ["history_x", "history_y"])
@pytest.mark.parametrize("copy_name", ["compatibility", "unit"])
def test_mas_contradictory_history_is_rejected_before_model_reconstruction(field, copy_name, monkeypatch):
    solver, adapter, _ = assembled("mas", mode="initialize")
    adapter.cfg.enable_surrogate = True
    adapter.cfg.surrogate_min_train_samples = 100
    assert solver.step().committed
    before = copy.deepcopy(adapter.get_state())
    corrupted = copy.deepcopy(before)
    if copy_name == "compatibility":
        corrupted[field][0][0] += 1.
    else:
        unit = adapter.unit_binding.restore(corrupted["algorithm_unit"])
        getattr(unit, field)[0][0] += 1.
        corrupted["algorithm_unit"] = adapter.unit_binding.dump(unit)
    monkeypatch.setattr(adapter, "_restore_surrogate_from_history",
                        lambda **kwargs: pytest.fail("contradictory history reached model reconstruction"))
    with pytest.raises(ValueError, match="authoritative Unit"):
        adapter.set_state(corrupted)
    assert adapter.get_state() == before
