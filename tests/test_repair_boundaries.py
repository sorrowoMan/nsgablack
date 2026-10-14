"""Real Unit owners across repair, admission and schedule commit boundaries."""
import numpy as np
import pytest

from blackbase.types import CandidateBatch, UnknownState
from nsgablack.adapters import (CompositeAdapter, GaussianSearchAdapter, GradientOptimizerAdapter,
    GradientDescentAdapter, SimulatedAnnealingAdapter, PatternSearchAdapter,
    TrustRegionDFOAdapter, StrategyChainAdapter, SerialPhaseSpec)
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.state.step_outcome import StepOutcome
from nsgablack.representation import JointRepairPolicy, RepresentationPipeline
from tests.test_joint_repair import Owner, UnitProjection, ProblemBounds, build
from tests.test_joint_repair_orchestration import Select


class Sphere(BlackBoxProblem):
    def __init__(self, dimension=1):
        super().__init__(dimension=dimension, objectives=["minimize"], bounds=[(-10, 10)] * dimension)
    def evaluate(self, x):
        return [float(np.sum(x * x))]


def seed_gaussian():
    adapter = GaussianSearchAdapter(population_size=1)
    adapter.set_current_candidates((UnknownState([1.], {"tag": "original"}),), [[1.]], [0.])
    return adapter


@pytest.mark.parametrize("change", ["value", "metadata"])
def test_gaussian_feedback_revision_survives_codec_and_invalidates_on_content_change(change):
    adapter = seed_gaussian()
    saved = adapter.get_state()
    if change == "value":
        adapter.algorithm_unit.best[:] = 9.
    else:
        adapter.algorithm_unit.candidate_metadata["tag"] = "changed"
    assert adapter.best_score is None and adapter.best_violation is None
    clone = GaussianSearchAdapter(population_size=1)
    clone.set_state(adapter.get_state())
    assert clone.best_score is None and clone.best_violation is None
    clone.set_state(saved)
    assert clone.best_score == 1. and clone.best_violation == 0.


def test_stale_candidate_feedback_is_rejected_by_feature_reads_and_old_schema_restore():
    from nsgablack.units import UnitFeature
    from nsgablack.units.features import FeatureContractError
    adapter = seed_gaussian()
    feature = UnitFeature("score", ("candidate_feedback",),
                          lambda inputs: inputs["candidate_feedback"]["best_score"]["value"],
                          feedback_view="selection")
    assert adapter.algorithm_unit.feature(feature) == 1.
    adapter.algorithm_unit.best[:] = 9.
    with pytest.raises(FeatureContractError, match="Candidate changed"):
        adapter.algorithm_unit.feature(feature)
    state = adapter.unit_binding.dump(adapter.algorithm_unit)
    state["contract"]["schema"]["version"] = 1
    with pytest.raises(ValueError, match="schema differs"):
        adapter.unit_binding.restore(state)


def test_unit_repair_cannot_keep_a_gaussian_incumbents_old_score():
    class Repair:
        def repair(self, unit, evidence, context):
            unit.best = np.array([9.])
            return CandidateBatch.from_candidates([state.with_values([2.]) for state in evidence.after.semantic_states],
                                                 candidate_tokens=evidence.after.candidate_tokens)
        def validate(self, unit, evidence, context):
            return bool(np.all(evidence.after.numeric_matrix == 2.))
    adapter = seed_gaussian()
    adapter.set_unit_repair(Repair())
    solver = ComposableSolver(Sphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(repair=ProblemBounds(high=10.)),
        joint_repair_policy=JointRepairPolicy())
    assert solver.step().committed
    assert adapter.best_x[0] == 2. and adapter.best_score == 4.


@pytest.mark.parametrize("factory,point,score", [
    (SimulatedAnnealingAdapter, "current_x", "current_score"),
    (PatternSearchAdapter, "current_x", "current_score"),
    (GradientDescentAdapter, "current_x", "current_score"),
    (TrustRegionDFOAdapter, "_center", "_best_score"),
])
def test_other_trajectory_scores_cannot_rank_changed_points(factory, point, score):
    owner = factory()
    setattr(owner, point, np.array([1.]))
    setattr(owner, score, 0.1)
    saved = owner.get_state()
    getattr(owner, point)[:] = 4.
    assert getattr(owner, score) is None
    owner.set_state(saved)
    assert getattr(owner, score) == 0.1


@pytest.mark.parametrize("joint", [False, True])
@pytest.mark.parametrize("sibling_commits", [False, True])
def test_problem_only_repair_rolls_back_rejected_gradient_unit(joint, sibling_commits):
    gradient = GradientOptimizerAdapter()
    gradient.current_x = np.array([0.8])
    gradient.current_score = 0.64
    root = CompositeAdapter([gradient, Owner("sibling", (0.3,))]) if sibling_commits else gradient
    solver = ComposableSolver(Sphere(), adapter=root,
        representation_pipeline=RepresentationPipeline(repair=ProblemBounds(high=0.4)),
        joint_repair_policy=JointRepairPolicy() if joint else None)
    before = gradient.unit_binding.dump(gradient.algorithm_unit)
    solver.evaluation_acceptance_policy = Select((1,) if sibling_commits else ())
    outcome = solver.step()
    assert outcome.committed == sibling_commits
    assert gradient.unit_binding.dump(gradient.algorithm_unit) == before
    assert gradient.current_score == 0.64 and not gradient._proposal_pending
    assert solver.evaluation_count == (2 if sibling_commits else 1)


def test_problem_only_repair_budget_race_restores_owner(monkeypatch):
    gradient = GradientOptimizerAdapter()
    gradient.current_x = np.array([0.8])
    gradient.current_score = 0.64
    solver = ComposableSolver(Sphere(), adapter=gradient,
        representation_pipeline=RepresentationPipeline(repair=ProblemBounds(high=0.4)))
    monkeypatch.setattr(solver, "_evaluate_population_with_budget_retry",
        lambda population: (np.empty((0, 1)), np.empty((0, 1)), np.empty(0), True))
    outcome = solver.step()
    assert outcome.status == "rejected" and outcome.evaluations == 0
    assert gradient.current_x[0] == 0.8 and gradient.current_score == 0.64


@pytest.mark.parametrize("double_compact", [False, True])
def test_real_finite_difference_partial_admission_compacts_coordinates_once(double_compact):
    calls = []
    class Repair:
        def repair(self, unit, evidence, context):
            unit.best = np.array([8., 8.])
            return evidence.after
        def validate(self, unit, evidence, context):
            return bool(len(unit.probes) == len(evidence.proposal_indices)
                        and np.allclose(unit.displacements, evidence.after.numeric_matrix - unit.current))
        def project_admission(self, baseline, draft, evidence, disposition, context):
            calls.append((len(baseline.probes), len(draft.probes), disposition.accepted_indices))
            assert len(baseline.probes) == 4 and len(draft.probes) == 2
            if double_compact:
                draft.probes = draft.probes[::-1]
                draft.directions = draft.directions[::-1].copy()
                draft.displacements = draft.displacements[::-1].copy()
            draft.best = baseline.best
            return draft
    owner = GradientDescentAdapter(max_directions=2)
    owner.current_x = np.array([0., 0.])
    owner.set_unit_repair(Repair())
    solver = ComposableSolver(Sphere(2), adapter=owner,
        representation_pipeline=RepresentationPipeline(repair=ProblemBounds(low=-10., high=10.)),
        joint_repair_policy=JointRepairPolicy())
    solver.evaluation_acceptance_policy = Select((1, 3))
    before = owner.get_state()
    if double_compact:
        with pytest.raises(ValueError, match="admitted coordinates"):
            solver.step()
        assert owner.get_state() == before
    else:
        assert solver.step().committed
        assert len(owner.algorithm_unit.probes) == 2 and owner.algorithm_unit.best is None
    assert calls == [(4, 2, (1, 3))] and solver.evaluation_count == 4


@pytest.mark.parametrize("algorithm", ["de", "moead"])
def test_population_pending_coordinates_are_projected_after_partial_disposition(algorithm):
    from nsgablack.adapters import DifferentialEvolutionAdapter, MOEADAdapter
    class BiSphere(BlackBoxProblem):
        def __init__(self):
            super().__init__(dimension=2, objectives=["minimize", "minimize"], bounds=[(-10, 10)] * 2)
        def evaluate(self, x):
            return [float(np.sum(x * x)), float(np.sum((x - 1.) ** 2))]
    owner = (DifferentialEvolutionAdapter(population_size=4, batch_size=4) if algorithm == "de" else
             MOEADAdapter(population_size=4, batch_size=4, neighborhood_size=4,
                          weight_generation="random", variation="de"))
    field = owner.admission_unit_fields[0]
    seen = []
    class Repair:
        def repair(self, unit, evidence, context):
            return CandidateBatch.from_candidates(
                [state.with_values(np.full(2, 0.125)) for state in evidence.after.semantic_states],
                candidate_tokens=evidence.after.candidate_tokens)
        def validate(self, unit, evidence, context):
            return len(getattr(unit, field)) == len(evidence.proposal_indices)
        def project_admission(self, baseline, draft, evidence, disposition, context):
            assert len(getattr(baseline, field)) == 4
            expected = [getattr(baseline, field)[i] for i in disposition.accepted_indices]
            assert list(getattr(draft, field)) == expected
            seen.append(disposition.accepted_indices)
            return draft
    solver = ComposableSolver(BiSphere(), adapter=owner,
        representation_pipeline=RepresentationPipeline(repair=ProblemBounds(low=-10., high=10.)))
    owner.setup(solver)
    # This test concerns post-bootstrap target coordinates. Establish the
    # initial population through the normal evaluation/admission transaction.
    assert solver.step().committed
    if algorithm == "moead":
        assert owner.pool_views_ready
    owner.set_unit_repair(Repair())
    solver.joint_repair_policy = JointRepairPolicy()
    before = solver.evaluation_count
    solver.evaluation_acceptance_policy = Select((1, 3))
    assert solver.step().committed
    assert seen == [(1, 3)] and solver.evaluation_count - before == 4


def test_doctor_rejects_malformed_admitted_coordinate_declarations():
    from nsgablack.core.joint_repair import inspect_joint_repair_contracts
    owner = Owner()
    owner.set_unit_repair(UnitProjection())
    solver, _, _ = build(owner, ProblemBounds())
    owner.admission_unit_fields = ("missing",)
    issues = inspect_joint_repair_contracts(solver, (owner,))
    assert any(code == "joint-repair-contract-invalid" and "admission_unit_fields" in message
               for code, message in issues)


def chain(name, can_advance=True, *, chain_type=StrategyChainAdapter, old=None):
    bad = old or Owner(name + "bad")
    bad.set_unit_repair(UnitProjection())
    phases = [SerialPhaseSpec("bad", bad)]
    if can_advance:
        good = Owner(name + "good", (1.2,))
        good.set_unit_repair(UnitProjection(low=1., high=1.5))
        phases.append(SerialPhaseSpec("good", good))
    return chain_type(phases, name=name)


def advancing_solver(root):
    solver, _, _ = build(root, ProblemBounds(low=1.))
    solver.joint_repair_policy = JointRepairPolicy(on_rejection="advance")
    root.setup(solver)
    return solver


def test_multi_branch_advance_is_planned_before_any_phase_changes():
    left, right = chain("left"), chain("right", False)
    solver = advancing_solver(CompositeAdapter([left, right]))
    outcome = solver.step()
    assert outcome.status == "rejected" and outcome.stop_requested
    assert left._current_idx == right._current_idx == 0
    assert not left._pending_phase_retirements and solver.evaluation_count == 0


def test_multi_branch_advance_applies_all_and_retires_each_phase_once():
    cleanup = []
    class Closed(Owner):
        def teardown(self, control):
            cleanup.append(self.name)
    left, right = chain("left", old=Closed("oldleft")), chain("right", old=Closed("oldright"))
    root = CompositeAdapter([left, right])
    solver = advancing_solver(root)
    outcome = solver.step()
    assert outcome.status == "rejected" and not outcome.stop_requested
    assert left._current_idx == right._current_idx == 1
    assert set(cleanup) == {"oldleft", "oldright"}
    root.teardown(solver)
    assert len(cleanup) == 2


def test_cancellation_after_schedule_apply_rolls_back_before_cleanup():
    from blackbase.resources import CancellationRef, CancellationToken, CancellationRequested
    token = CancellationToken(CancellationRef(backend="memory"))
    class CancelRoot(CompositeAdapter):
        def on_joint_repair_rejected(self, control, report):
            result = super().on_joint_repair_rejected(control, report)
            token.cancel("after schedule apply")
            return result
    class Runtime:
        def checkpoint(self):
            token.checkpoint()
    child = chain("child")
    solver = advancing_solver(CancelRoot([child]))
    solver.set_case_runtime(Runtime())
    with pytest.raises(CancellationRequested):
        solver.step()
    assert child._current_idx == 0 and not child._pending_phase_retirements
    assert not child._retired_in_process


def test_schedule_apply_failure_rolls_back_every_branch_without_teardown():
    cleanup = []
    class CleanupOwner(Owner):
        def teardown(self, control):
            cleanup.append(self.name)
    class BrokenChain(StrategyChainAdapter):
        def plan_repair_rejection_advance(self, control, report, owner_path):
            plan = super().plan_repair_rejection_advance(control, report, owner_path)
            def fail():
                raise RuntimeError("schedule apply failed")
            return (*plan, fail)
    left = chain("left", old=CleanupOwner("oldleft"))
    right = chain("right", chain_type=BrokenChain)
    solver = advancing_solver(CompositeAdapter([left, right]))
    with pytest.raises(RuntimeError, match="schedule apply failed"):
        solver.step()
    assert left._current_idx == right._current_idx == 0
    assert not left._pending_phase_retirements and not right._pending_phase_retirements
    assert cleanup == [] and solver.evaluation_count == 0


def test_phase_cleanup_failure_preserves_applied_schedule_and_retry_queue():
    attempts = []
    class Flaky(Owner):
        def teardown(self, control):
            attempts.append(self.name)
            if len(attempts) == 1:
                raise RuntimeError("release failed")
    root = chain("chain", old=Flaky("old"))
    solver = advancing_solver(root)
    outcome = solver.step()
    assert outcome.status == "rejected" and not outcome.stop_requested
    assert root._current_idx == 1 and root._pending_phase_retirements == [0]
    assert not outcome.metadata["adapter_post_commit_cleanup"]["cleanup_complete"]
    saved = root.get_state()
    root.set_state(saved)
    assert root._pending_phase_retirements == [0]
    assert solver.step().committed
    assert root._current_idx == 1 and not root._pending_phase_retirements and len(attempts) == 2


def test_invalid_rejection_hook_result_rolls_back_its_own_mutations():
    class Broken(Owner):
        def on_joint_repair_rejected(self, control, report):
            self.algorithm_unit.current[:] = 99.
            return StepOutcome(status="committed")
    owner = Broken()
    owner.set_unit_repair(UnitProjection())
    solver, _, _ = build(owner, ProblemBounds(low=1.))
    before = owner.get_state()
    with pytest.raises(TypeError, match="zero-evaluation"):
        solver.step()
    assert owner.get_state() == before
