"""Joint validity belongs to the final version, not the last repair callback."""
import numpy as np
import pytest

from blackbase.types import CandidateBatch, UnknownState
from nsgablack.adapters import CompositeAdapter, RoleAdapter
from nsgablack.adapters.unit_backed import UnitBackedAdapter
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.state.step_outcome import StepOutcome
from nsgablack.representation import RepresentationPipeline, TrajectoryUnitBuilder, JointRepairPolicy
from nsgablack.utils.runtime_contracts import inspect_runtime_contracts


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimize"], bounds=[(0., 2.)])
        self.seen = []
    def evaluate(self, candidate):
        self.seen.append(np.array(candidate, copy=True))
        return [float(candidate[0])]


class Owner(UnitBackedAdapter):
    unit_builder_type = TrajectoryUnitBuilder
    unit_schema = TrajectoryUnitBuilder.unit_type.schema
    accepts_proposal_replacement = True

    def __init__(self, name="owner", candidates=(0.2,)):
        super().__init__(name)
        self.values = candidates
        self.ensure_unit().current = np.array([0.25])
        self.rejections = []
        self.observed_local = []
    def propose(self, control, context):
        self.ensure_unit()
        return [UnknownState([value], {"row": i}) for i, value in enumerate(self.values)]
    def on_proposal_repair(self, control, evidence, context):
        self.observed_local.append((evidence.proposal_indices, dict(context)))
        if evidence.after.semantic_states:
            self.algorithm_unit.current = evidence.after.numeric_matrix[0].copy()
    def update(self, control, candidates, feedback, context):
        self.algorithm_unit.current = np.array(candidates[0], copy=True)
    def on_joint_repair_rejected(self, control, report):
        unit = self.algorithm_unit
        self.rejections.append((report, None if unit is None else unit.current.copy()))
        return super().on_joint_repair_rejected(control, report)


class ProblemBounds:
    def __init__(self, low=0., high=2.):
        self.low, self.high = low, high
        self.repairs, self.validated = [], []
    def repair(self, candidate, context):
        self.repairs.append(np.array(candidate, copy=True))
        return np.clip(candidate, self.low, self.high)
    def validate(self, candidate, context):
        self.validated.append(candidate)
        return bool(np.all((candidate.values >= self.low) & (candidate.values <= self.high)))


class UnitProjection:
    def __init__(self, low=0., high=0.5):
        self.low, self.high, self.drafts = low, high, []
        self.validated_units = []
    def repair(self, unit, evidence, context):
        self.drafts.append(unit)
        result = CandidateBatch.from_candidates(
            [state.with_values(np.clip(state.values, self.low, self.high)) for state in evidence.after.semantic_states],
            candidate_tokens=evidence.after.candidate_tokens)
        unit.current = result.numeric_matrix[0].copy()
        return result
    def validate(self, unit, evidence, context):
        self.validated_units.append(unit)
        return bool(np.all((evidence.after.numeric_matrix >= self.low) & (evidence.after.numeric_matrix <= self.high))
                    and np.array_equal(unit.current, evidence.after.numeric_matrix[0]))


def build(owner=None, problem_repair=None, rounds=1):
    owner = owner or Owner()
    repair = problem_repair or ProblemBounds()
    solver = ComposableSolver(Problem(), adapter=owner,
        representation_pipeline=RepresentationPipeline(repair=repair), joint_repair_policy=JointRepairPolicy(rounds))
    return solver, owner, repair


def test_unit_repair_candidate_changes_are_revalidated_and_receipt_is_persisted():
    owner = Owner(candidates=(1.5,))
    unit_repair = UnitProjection()
    owner.set_unit_repair(unit_repair)
    solver, _, repair = build(owner)
    outcome = solver.step()
    assert outcome.committed
    assert repair.validated[0].values[0] == 0.5  # not the pre-UnitRepair value 1.5
    np.testing.assert_array_equal(solver.problem.seen, [[0.5]])
    assert outcome.metadata["joint_repair"]["status"] == "verified"
    assert outcome.metadata["joint_repair"]["unit_revisions"]
    edge = outcome.metadata["evaluation_disposition"]["disposition_payload"]
    assert edge["joint_repair"] == outcome.metadata["joint_repair"]
    assert solver.get_candidate_population_batch().semantic_states[0].metadata["row"] == 0
    unit_repair.drafts[0].current[:] = 100
    for retained in unit_repair.validated_units:
        retained.current[:] = 999
    np.testing.assert_array_equal(owner.algorithm_unit.current, [0.5])


def test_empty_intersection_rejects_without_evaluation_and_restores_authority():
    owner = Owner(candidates=(0.2,))
    owner.set_unit_repair(UnitProjection(high=0.5))
    solver, _, repair = build(owner, ProblemBounds(low=1.), rounds=5)
    before = owner.get_state()
    outcome = solver.step()
    assert outcome.status == "rejected" and outcome.evaluations == 0
    assert outcome.metadata["joint_repair"]["reason"] == "repair_cycle"
    assert len(repair.repairs) == 2
    assert not solver.problem.seen and solver.evaluation_count == 0
    assert owner.get_state() == before
    assert not owner.observed_local  # no adoption/reconciliation on invalid pair
    np.testing.assert_array_equal(owner.rejections[0][1], [0.25])
    assert solver._latest_snapshot_handle is None and solver.pending_snapshot_step_key() is None


def test_bounded_rounds_can_find_a_jointly_valid_pair_without_mutating_owner_between_rounds():
    class MoveTowardFeasible(UnitProjection):
        def repair(self, unit, evidence, context):
            assert unit.current[0] == 0.25
            result = CandidateBatch.from_candidates(
                [state.with_values(state.values + 0.4) for state in evidence.after.semantic_states],
                candidate_tokens=evidence.after.candidate_tokens)
            unit.current = result.numeric_matrix[0].copy()
            return result
    class Validator(ProblemBounds):
        def validate(self, candidate, context):
            return bool(candidate.values[0] >= 1.)
    owner = Owner(candidates=(0.2,))
    owner.set_unit_repair(MoveTowardFeasible(high=2.))
    solver, _, _ = build(owner, Validator(), rounds=3)
    outcome = solver.step()
    assert outcome.committed and outcome.metadata["joint_repair"]["rounds"] == 2
    assert len(owner.observed_local) == 1
    np.testing.assert_allclose(solver.problem.seen, [[1.]])


def test_problem_repair_can_break_unit_invariant_and_unit_validator_rejects_it():
    class NoProjection(UnitProjection):
        def repair(self, unit, evidence, context):
            unit.current = evidence.after.numeric_matrix[0].copy()
            return evidence.after
    owner = Owner()
    owner.set_unit_repair(NoProjection(high=0.5))
    solver, _, _ = build(owner, ProblemBounds(low=1.))
    outcome = solver.step()
    assert outcome.status == "rejected"
    assert outcome.metadata["joint_repair"]["problem_valid"] is True
    assert outcome.metadata["joint_repair"]["unit_valid"] is False
    assert not solver.problem.seen


def test_structure_only_repair_preserves_problem_version():
    class StructureOnly(UnitProjection):
        def repair(self, unit, evidence, context):
            unit.best = np.array([0.1])
            unit.current = evidence.after.numeric_matrix[0].copy()
            return evidence.after
    owner = Owner()
    owner.set_unit_repair(StructureOnly())
    solver, _, _ = build(owner)
    assert solver.step().committed
    np.testing.assert_array_equal(owner.algorithm_unit.best, [0.1])


def test_nested_nonprefix_local_selection_and_budget_preserve_repair_ownership():
    from blackbase.contracts import BatchDisposition
    class NonprefixRole(RoleAdapter):
        def propose(self, control, context):
            values = list(self.inner.propose(control, context))
            self._inner_proposal_disposition = BatchDisposition(proposed_count=3, accepted_indices=(1, 2), reason="test")
            return [values[1], values[2]]
    left, right = Owner("left", (0.1, 0.2, 0.3)), Owner("right", (1.2, 1.3))
    left.set_unit_repair(UnitProjection())
    right.set_unit_repair(UnitProjection(low=1., high=1.5))
    root = CompositeAdapter([NonprefixRole("left_role", left), RoleAdapter("right_role", right)])
    solver, _, _ = build(root)
    solver.evaluation_batch_allowance = lambda count, context: 3
    assert solver.step().committed
    np.testing.assert_array_equal(solver.problem.seen, [[0.2], [0.3], [1.2]])
    assert left.observed_local[0][0] == (1, 2)
    assert right.observed_local[0][0] == (0,)
    assert right.observed_local[0][1]["role"] == "right_role"


@pytest.mark.parametrize("fault", ["tokens", "unit_id", "validator_type", "validator_mutation", "raise"])
def test_invalid_unit_repair_contracts_fail_and_rollback(fault):
    class Invalid(UnitProjection):
        def repair(self, unit, evidence, context):
            result = super().repair(unit, evidence, context)
            if fault == "tokens":
                return CandidateBatch.from_candidates(result.semantic_states, candidate_tokens=("other",))
            if fault == "unit_id":
                unit.unit_id = "other"
            if fault == "raise":
                raise TypeError("callback error")
            return result
        def validate(self, unit, evidence, context):
            if fault == "validator_type":
                return None
            if fault == "validator_mutation":
                unit.current[:] = 0.4
            return True
    owner = Owner()
    owner.set_unit_repair(Invalid())
    solver, _, _ = build(owner)
    before = owner.get_state()
    with pytest.raises((ValueError, TypeError)):
        solver.step()
    assert not solver.problem.seen and owner.get_state() == before


def test_reconciliation_cannot_invalidate_a_previously_valid_unit():
    class CorruptOwner(Owner):
        def on_proposal_repair(self, *args):
            self.algorithm_unit.current = np.array([100.])
    owner = CorruptOwner()
    owner.set_unit_repair(UnitProjection())
    solver, _, _ = build(owner)
    result = solver.step()
    assert result.status == "rejected"
    assert result.metadata["joint_repair"]["reason"] == "owner_reconciliation_invalid"
    np.testing.assert_array_equal(owner.algorithm_unit.current, [0.25])
    assert not solver.problem.seen


def test_doctor_does_not_execute_validators_and_rejects_missing_contract():
    class Never(ProblemBounds):
        def validate(self, *args):
            pytest.fail("Doctor ran validation")
    solver, owner, _ = build(problem_repair=Never())
    owner.set_unit_repair(UnitProjection())
    assert not [c for c, _ in inspect_runtime_contracts(solver) if c == "joint-repair-contract-invalid"]
    solver.joint_repair_policy = None
    assert any(c == "joint-repair-contract-invalid" for c, _ in inspect_runtime_contracts(solver))
    with pytest.raises(TypeError, match="UnitRepair requires"):
        solver.step()


def test_adapter_can_stop_after_rejection_but_cannot_report_a_commit():
    class Stop(Owner):
        def on_joint_repair_rejected(self, control, report):
            return StepOutcome(status="cancelled", proposals=report["proposed_count"], stop_requested=True)
    owner = Stop()
    owner.set_unit_repair(UnitProjection())
    solver, _, _ = build(owner, ProblemBounds(low=1.))
    result = solver.step()
    assert result.status == "cancelled" and result.stop_requested
    owner.on_joint_repair_rejected = lambda control, report: StepOutcome(status="committed")
    with pytest.raises(TypeError, match="zero-evaluation"):
        solver.step()


def test_policy_requires_finite_positive_round_budget():
    for value in (0, -1, True, 1.5):
        with pytest.raises(ValueError):
            JointRepairPolicy(value)


def test_evolution_uses_joint_repair_in_its_existing_outer_transaction():
    from nsgablack.core import EvolutionSolver
    class RejectPopulation:
        def repair(self, unit, evidence, context):
            return evidence.after
        def validate(self, unit, evidence, context):
            return False
    solver = EvolutionSolver(Problem(), pop_size=2, max_generations=1,
        representation_pipeline=RepresentationPipeline(repair=ProblemBounds()),
        joint_repair_policy=JointRepairPolicy())
    solver.adapter.set_population_snapshot(np.full((2, 1), 0.2), np.zeros((2, 1)), np.zeros(2))
    solver.adapter.set_unit_repair(RejectPopulation())
    before = solver.adapter.get_state()
    assert solver.step().status == "rejected"
    assert solver.history == [] and not solver.problem.seen
    assert solver.adapter.get_state() == before


def test_unit_metadata_change_invalidates_problem_validation():
    class TaggedProblem(ProblemBounds):
        def validate(self, candidate, context):
            return candidate.metadata.get("allowed", True)
    class Retag(UnitProjection):
        def repair(self, unit, evidence, context):
            unit.current = evidence.after.numeric_matrix[0].copy()
            return CandidateBatch.from_candidates(
                [state.with_meta(allowed=False) for state in evidence.after.semantic_states],
                candidate_tokens=evidence.after.candidate_tokens)
    owner = Owner()
    owner.set_unit_repair(Retag())
    solver, _, _ = build(owner, TaggedProblem())
    assert solver.step().status == "rejected" and not solver.problem.seen


def test_wrapper_reconciliation_override_is_not_skipped_by_shared_routing():
    seen = []
    class HookedRole(RoleAdapter):
        def on_proposal_repair(self, control, repair, context):
            seen.append(self.role)
            super().on_proposal_repair(control, repair, context)
    owner = Owner()
    owner.set_unit_repair(UnitProjection())
    solver, _, _ = build(CompositeAdapter([HookedRole("wrapped", owner)]))
    assert solver.step().committed and seen == ["wrapped"]
