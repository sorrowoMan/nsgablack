from dataclasses import dataclass

import numpy as np
import pytest

from blackbase.participation import ParticipationContract, ParticipationViolation
from blackbase.plugin import PluginBase, PluginManager
from blackbase.preferences import PreferenceDelta
from blackbase.representation import RepresentationCapabilities, representation_capabilities
from blackbase.runtime import RuntimeTransaction, AuthorityRegistry, FinalizationHooks
from blackbase.types import Feedback
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.blank_solver import SolverBase
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.state.population_authority import PopulationAuthority
from nsgablack.utils.runtime_contracts import inspect_runtime_contracts


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="contract", dimension=1, bounds={"x0": (-2, 2)})

    def evaluate(self, candidate):
        return Feedback(objectives=[2.0], info={"constraint_violation": 3.0})


class Preference:
    preference_keys = ("objectives.0",)

    def preferences(self, candidate, feedback, context):
        return (PreferenceDelta("objectives.0", -0.5, "prefer lower selection score"),)


@pytest.mark.parametrize("batch", [False, True])
def test_preference_keeps_measurement_and_violation_through_wire_roundtrip(batch):
    solver = SolverBase(Problem(), bias_module=Preference(), ignore_constraint_violation_when_bias=True)
    if batch:
        selected, violations = solver.evaluate_population(np.asarray([[0.0], [1.0]]))
        feedback = solver.get_last_feedback_batch()
    else:
        selected, violation = solver.evaluate_individual(np.array([0.0]))
        violations = np.asarray([violation])
        feedback = OptimizationFeedbackBatch.from_feedback((solver._last_individual_feedback,))
    assert np.allclose(selected, 1.5)
    assert np.allclose(violations, 0.0)
    recovered = OptimizationFeedbackBatch.from_dict(feedback.as_dict())
    assert np.allclose(recovered.raw_objectives, 2.0)
    assert np.allclose(recovered.raw_violations, 3.0)
    assert recovered.items[0].info["preference_deltas"][0]["reason"] == "prefer lower selection score"


def test_preference_cannot_write_undeclared_or_hard_constraint_key():
    class Forbidden(Preference):
        def preferences(self, candidate, feedback, context):
            return (PreferenceDelta("constraints.0", -3.0, "erase violation"),)

    solver = SolverBase(Problem(), bias_module=Forbidden())
    with pytest.raises(ValueError, match="undeclared key"):
        solver.evaluate_individual(np.array([0.0]))


@pytest.mark.parametrize("batch", [False, True])
def test_provider_short_circuit_keeps_raw_feedback_with_preferences(batch):
    from nsgablack.plugins import EvaluationModelConfig, EvaluationModelProviderPlugin

    class UnusedProblem(Problem):
        def evaluate(self, candidate):
            pytest.fail("registered provider must supply this evaluation")

    class Backend:
        def solve(self, request):
            return {"status": "ok", "objective": 2.0, "violation": 3.0}

    solver = SolverBase(UnusedProblem(), bias_module=Preference())
    solver.register_evaluation_provider(EvaluationModelProviderPlugin(
        config=EvaluationModelConfig(scope="outer", warn_on_failure=False),
        backend_factory=lambda problem, context: Backend(),
    ).create_provider())
    if batch:
        objectives, violations = solver.evaluate_population(np.array([[0.0], [1.0]]))
        feedback = solver.get_last_feedback_batch()
    else:
        objectives, violations = solver.evaluate_individual(np.array([0.0]))
        feedback = OptimizationFeedbackBatch.from_feedback((solver._last_individual_feedback,))
    assert np.allclose(objectives, 1.5)
    assert np.allclose(violations, 3.0)
    recovered = OptimizationFeedbackBatch.from_dict(feedback.as_dict())
    assert np.allclose(recovered.raw_objectives, 2.0)
    assert np.allclose(recovered.raw_violations, 3.0)


def test_solver_compatibility_fields_have_exactly_one_owner():
    solver = SolverBase(Problem())
    solver.population = np.asarray([[1.0]])
    solver._resume_cursor = 4
    assert solver.population is solver.population_authority.population
    assert solver.run_session.resume_cursor == 4
    assert "population" not in vars(solver)
    assert "_resume_cursor" not in vars(solver)
    assert inspect_runtime_contracts(solver) == ()


def test_new_authority_state_field_is_automatically_rolled_back():
    @dataclass
    class ExtendedAuthority(PopulationAuthority):
        proposal_epoch: int = 0

    owner = ExtendedAuthority(population=np.asarray([[1.0]]))
    transaction = RuntimeTransaction((owner,))
    owner.population[0, 0] = 9.0
    owner.proposal_epoch = 7
    transaction.rollback()
    assert owner.population[0, 0] == 1.0
    assert owner.proposal_epoch == 0


def test_representation_declaration_is_required_and_verified():
    class Implicit:
        initializer = True

        def init(self, context):
            return [0.0]

    with pytest.raises(TypeError, match="must declare"):
        representation_capabilities(Implicit())
    Implicit.representation_capabilities = RepresentationCapabilities(frozenset({"decode"}))
    with pytest.raises(TypeError, match="unavailable: decode"):
        representation_capabilities(Implicit())


def test_declared_representation_is_checked_by_same_doctor_validator():
    solver = SolverBase(Problem())
    solver.representation_pipeline = object()
    assert inspect_runtime_contracts(solver)[0][0] == "representation-capabilities-invalid"


def test_evolution_and_trajectory_consumers_use_declared_mutation_without_marker():
    import warnings
    from nsgablack.core.evolution_solver import EvolutionSolver
    from nsgablack.adapters import VNSAdapter, SimulatedAnnealingAdapter

    class Pipeline:
        representation_capabilities = RepresentationCapabilities(frozenset({"mutate"}))
        context_requires = ("vns_k",)

        def mutate(self, value, context=None):
            return np.asarray(value) + 0.25

    solver = EvolutionSolver(Problem(), representation_pipeline=Pipeline())
    assert np.allclose(solver.mutate(np.array([[0.0], [1.0]])), [[0.25], [1.25]])
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        VNSAdapter()._warn_if_pipeline_does_not_consume_context(solver)
        SimulatedAnnealingAdapter()._warn_if_pipeline_has_no_mutator(solver)
    assert captured == []


def test_observer_cannot_silently_gain_evaluation_or_publication_veto():
    class EvaluationObserver(PluginBase):
        def evaluate_individual(self, *args):
            return [0.0], 0.0

    class PublicationObserver(PluginBase):
        def on_solver_finalization_prepare(self, result):
            raise RuntimeError("veto")

    manager = PluginManager()
    for plugin in (EvaluationObserver("eval"), PublicationObserver("publish")):
        with pytest.raises(ParticipationViolation):
            manager.register(plugin)
    PublicationObserver.participation = ParticipationContract(vetoes=("finalization",))
    manager.register(PublicationObserver("allowed"))


def test_duplicate_authority_and_partial_finalization_are_rejected():
    registry = AuthorityRegistry()
    registry.register("population", PopulationAuthority())
    with pytest.raises(ValueError, match="owner conflict"):
        registry.register("population", object())
    with pytest.raises(TypeError, match="requires prepare, freeze and abort"):
        FinalizationHooks(prepare=lambda result: result)


def test_doctor_checks_child_snapshot_without_restoring_or_committing():
    class Invalid(PopulationAuthority):
        name = "invalid-child"

        def snapshot_step_state(self):
            return object()

        def restore_step_state(self, state):
            pytest.fail("inspection must not restore")

        def commit_step_state(self, state):
            pytest.fail("inspection must not release resources")

    class Parent(PopulationAuthority):
        name = "parent"

        def step_transaction_children(self):
            return (child, child)

    child = Invalid()
    solver = SolverBase(Problem())
    solver.register_state_participant(Parent())
    issues = inspect_runtime_contracts(solver)
    assert [code for code, _ in issues] == ["runtime-participant-snapshot-invalid"]
    assert "invalid-child" in issues[0][1]


def test_doctor_validates_rollback_contract_of_every_registered_fact():
    solver = SolverBase(Problem())
    owner = PopulationAuthority()
    solver.authorities.register("custom_fact", owner)
    owner.rollback_exempt_reason = "owner policy changed without re-registration"
    assert any(code == "authority-rollback-contract-invalid" and "custom_fact" in message
               for code, message in inspect_runtime_contracts(solver))


def test_run_session_exemption_rejects_accidental_transaction_registration():
    solver = SolverBase(Problem())
    lock = solver.run_session.restore_lock
    for registration in solver.authorities.registrations():
        if registration.fact in {"progress", "result"}:
            assert registration.rollback_exempt_reason == solver.run_session.rollback_exempt_reason
    with pytest.raises(TypeError, match="RunSession is rollback-exempt"):
        solver.register_state_participant(solver.run_session)
    with pytest.raises(TypeError, match="RunSession is rollback-exempt"):
        RuntimeTransaction((solver.run_session,))
    assert solver.run_session.restore_lock is lock


def test_failed_physical_attempt_is_counted_without_committing_logical_progress():
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.core import ComposableSolver

    class Failing(AlgorithmAdapter):
        def propose(self, control, context):
            raise RuntimeError("attempt failed")

        def update(self, control, candidates, feedback, context):
            pytest.fail("failed proposal cannot reach update")

    solver = ComposableSolver(Problem(), adapter=Failing("failing"))
    lock = solver.run_session.restore_lock
    with pytest.raises(RuntimeError, match="attempt failed"):
        solver.run(max_steps=1)
    assert solver.run_session.attempts == 1
    assert solver.run_session.steps == 0
    assert solver.run_session.restore_lock is lock


@pytest.mark.parametrize("dispatch", ["trigger", "dispatch"])
def test_evaluation_permission_is_rechecked_after_registration(dispatch):
    class Evaluator(PluginBase):
        participation = ParticipationContract(decides=("evaluation",))

        def evaluate_individual(self, *args):
            pytest.fail("revoked participant must not execute")

    solver = SolverBase(Problem())
    plugin = Evaluator("revoked")
    solver.plugin_manager.register(plugin)
    plugin.participation = ParticipationContract()
    assert ("plugin-participation-invalid" in
            {code for code, _ in inspect_runtime_contracts(solver)})
    with pytest.raises(ParticipationViolation):
        getattr(solver.plugin_manager, dispatch)("evaluate_individual", [0.0])
