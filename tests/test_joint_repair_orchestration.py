"""Joint repair at admission, scheduling, cancellation and restore boundaries."""
import numpy as np
import pytest

from blackbase.contracts import BatchDisposition
from blackbase.resources import CancellationRef, CancellationToken, CancellationRequested
from nsgablack.adapters import CompositeAdapter, RoleAdapter, StrategyChainAdapter, SerialPhaseSpec
from nsgablack.representation import JointRepairPolicy
from tests.test_joint_repair import Owner, UnitProjection, ProblemBounds, build


class Select:
    def __init__(self, indices):
        self.indices = indices
    def select(self, candidates, feedback, context):
        return BatchDisposition(proposed_count=len(candidates.semantic_states),
                                accepted_indices=self.indices, reason="test_admission")


class ProjectableRepair(UnitProjection):
    def repair(self, unit, evidence, context):
        result = super().repair(unit, evidence, context)
        unit.best = np.array([0.123])
        return result
    def project_admission(self, baseline, draft, evidence, disposition, context):
        rows = [i for i, index in enumerate(evidence.proposal_indices) if index in disposition.accepted_indices]
        baseline.current = evidence.after.numeric_matrix[rows[0]].copy()
        baseline.best = draft.best.copy()
        return baseline


def test_successful_repair_followed_by_total_rejection_restores_unit_and_authority():
    owner = Owner(candidates=(0.2,))
    owner.set_unit_repair(ProjectableRepair())
    solver, _, _ = build(owner)
    assert solver.step().committed
    before, authority = owner.get_state(), solver.get_population_authority_identity()
    owner.values = (0.4,)
    solver.evaluation_acceptance_policy = Select(())
    outcome = solver.step()
    assert outcome.status == "rejected" and outcome.evaluations == 1
    assert owner.get_state() == before
    assert solver.get_population_authority_identity() == authority
    assert outcome.metadata["joint_repair"]["admission"][0]["accepted_indices"] == ()
    assert outcome.metadata["evaluation_disposition"]["status"] == "rejected"
    # Explicit Unit codec state remains safe to checkpoint/restore after rejection.
    restored = Owner()
    restored.set_state(owner.get_state())
    assert restored.get_state() == before


def test_zero_evaluation_budget_race_discards_unit_draft(monkeypatch):
    owner = Owner(candidates=(0.4,))
    owner.set_unit_repair(ProjectableRepair())
    solver, _, _ = build(owner)
    before = owner.get_state()
    monkeypatch.setattr(solver, "_evaluate_population_with_budget_retry",
                        lambda population: (np.empty((0, 1)), np.empty((0, 1)), np.empty(0), True))
    outcome = solver.step()
    assert outcome.reason == "evaluation_budget_race"
    assert owner.get_state() == before and not solver.problem.seen


def test_partial_nonprefix_admission_projects_unit_without_rerunning_repair():
    owner = Owner(candidates=(0.1, 0.4))
    component = ProjectableRepair()
    owner.set_unit_repair(component)
    solver, _, _ = build(CompositeAdapter([RoleAdapter("wrapped", owner)]))
    solver.evaluation_acceptance_policy = Select((1,))
    outcome = solver.step()
    assert outcome.committed and len(component.drafts) == 1
    np.testing.assert_array_equal(owner.algorithm_unit.current, [0.4])
    np.testing.assert_array_equal(owner.algorithm_unit.best, [0.123])
    admission = outcome.metadata["joint_repair"]["admission"][0]
    assert admission["accepted_indices"] == (1,)
    assert admission["owner_path"].endswith("/0:role:wrapped/0:owner")


def test_partial_admission_without_projection_fails_closed_and_preserves_event():
    owner = Owner(candidates=(0.1, 0.4))
    owner.set_unit_repair(UnitProjection())
    solver, _, _ = build(owner)
    solver.evaluation_acceptance_policy = Select((1,))
    before = owner.get_state()
    with pytest.raises(TypeError, match="project_admission"):
        solver.step()
    assert owner.get_state() == before and solver.evaluation_count == 2
    assert solver._last_evaluation_event_id


def test_one_rejected_child_does_not_keep_its_repaired_unit_when_sibling_commits():
    left, right = Owner("same", (0.1,)), Owner("same", (0.4,))
    for owner in (left, right):
        owner.set_unit_repair(ProjectableRepair())
    solver, _, _ = build(CompositeAdapter([left, right]))
    before = left.get_state()
    solver.evaluation_acceptance_policy = Select((1,))
    outcome = solver.step()
    assert outcome.committed and left.get_state() == before
    np.testing.assert_array_equal(right.algorithm_unit.current, [0.4])
    rows = outcome.metadata["joint_repair"]["admission"]
    assert len({row["owner_path"] for row in rows}) == 2


def test_failure_report_retains_nested_owner_and_original_indices_after_rollback():
    good, bad = Owner("same", (1.2,)), Owner("same", (0.2, 0.3))
    good.set_unit_repair(UnitProjection(low=1., high=1.5))
    bad.set_unit_repair(UnitProjection(high=0.5))
    solver, _, _ = build(CompositeAdapter([good, RoleAdapter("bad", bad)]), ProblemBounds(low=1.))
    outcome = solver.step()
    assert outcome.stop_requested and not solver.problem.seen
    failure = outcome.metadata["joint_repair"]["failures"][0]
    assert failure["owner_path"].endswith("/1:role:bad/0:same")
    assert failure["proposal_indices"] == (0, 1)
    assert failure["root_proposal_indices"] == (1, 2)
    assert len(set(failure["candidate_tokens"])) == 2


def test_explicit_advance_routes_through_wrapper_and_preserves_restore_state():
    bad, good = Owner("bad"), Owner("good", (1.2,))
    bad.set_unit_repair(UnitProjection(high=0.5))
    good.set_unit_repair(UnitProjection(low=1., high=1.5))
    chain = StrategyChainAdapter([SerialPhaseSpec("first", bad), SerialPhaseSpec("second", good)])
    root = RoleAdapter("outer", chain)
    solver, _, _ = build(root, ProblemBounds(low=1.))
    solver.joint_repair_policy = JointRepairPolicy(on_rejection="advance")
    chain.setup(solver)
    first = solver.step()
    assert first.status == "rejected" and not first.stop_requested
    assert first.metadata["repair_rejection_action"] == "advanced"
    assert chain._current_idx == 1 and chain._step_in_phase == 0
    checkpoint = chain.get_state()
    chain._current_idx = 0
    chain.set_state(checkpoint)
    assert chain._current_idx == 1
    assert solver.step().committed and len(solver.problem.seen) == 1


@pytest.mark.parametrize("action,stop", [("stop", True), ("retry", False), ("advance", True)])
def test_rejection_policy_is_explicit_and_unsupported_advance_stops(action, stop):
    owner = Owner()
    owner.set_unit_repair(UnitProjection())
    solver, _, _ = build(owner, ProblemBounds(low=1.))
    solver.joint_repair_policy = JointRepairPolicy(on_rejection=action)
    assert solver.step().stop_requested is stop


def test_cancellation_between_repair_rounds_rolls_back_without_evaluation():
    token = CancellationToken(CancellationRef(backend="memory"))
    class Runtime:
        def checkpoint(self):
            token.checkpoint()
    class CancelRepair(UnitProjection):
        def repair(self, unit, evidence, context):
            result = super().repair(unit, evidence, context)
            token.cancel("cancel during repair")
            return result
    owner = Owner()
    owner.set_unit_repair(CancelRepair())
    solver, _, repair = build(owner, ProblemBounds(low=1.), rounds=10)
    solver.set_case_runtime(Runtime())
    before = owner.get_state()
    with pytest.raises(CancellationRequested):
        solver.step()
    assert len(repair.repairs) == 1 and not solver.problem.seen
    assert owner.get_state() == before


@pytest.mark.parametrize("action", ["skip", "", None])
def test_invalid_rejection_policy_is_not_silently_ignored(action):
    with pytest.raises(ValueError, match="on_rejection"):
        JointRepairPolicy(on_rejection=action)


def test_default_rejection_stops_run_after_one_attempt():
    owner = Owner()
    owner.set_unit_repair(UnitProjection())
    solver, _, _ = build(owner, ProblemBounds(low=1.))
    result = solver.run(max_steps=3)
    assert result["step_attempts"] == 1 and result["steps"] == 0
    assert result["termination_reason"] == "joint_repair_rejected"


@pytest.mark.parametrize("fault", ["identity", "invariant"])
def test_invalid_partial_projection_rolls_back_but_keeps_evaluation_cost(fault):
    class Invalid(ProjectableRepair):
        def project_admission(self, baseline, draft, evidence, disposition, context):
            if fault == "identity":
                draft.unit_id = "another-unit"
            else:
                draft.current = np.array([999.])
            return draft
    owner = Owner(candidates=(0.1, 0.4))
    owner.set_unit_repair(Invalid())
    solver, _, _ = build(owner)
    solver.evaluation_acceptance_policy = Select((1,))
    before = owner.get_state()
    with pytest.raises(ValueError, match="identity|invalidated"):
        solver.step()
    assert owner.get_state() == before and solver.evaluation_count == 2


@pytest.mark.parametrize("stage,cost", [("reconciliation", 0), ("disposition", 1)])
def test_owner_callbacks_cannot_replace_repaired_unit_identity(stage, cost):
    class InvalidOwner(Owner):
        def on_proposal_repair(self, control, evidence, context):
            super().on_proposal_repair(control, evidence, context)
            if stage == "reconciliation":
                self.algorithm_unit.unit_id = "another-unit"
        def on_proposal_disposition(self, control, disposition, context):
            super().on_proposal_disposition(control, disposition, context)
            if stage == "disposition":
                self.algorithm_unit.unit_id = "another-unit"
    owner = InvalidOwner()
    owner.set_unit_repair(UnitProjection())
    solver, _, _ = build(owner)
    before = owner.get_state()
    with pytest.raises(ValueError, match="preserve Unit identity"):
        solver.step()
    assert owner.get_state() == before and solver.evaluation_count == cost
