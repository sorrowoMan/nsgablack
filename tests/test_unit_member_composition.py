"""Member maintenance through real repair, admission, commit and restore paths."""
from dataclasses import dataclass, field
import json

import numpy as np
import pytest

from blackbase.types import CandidateBatch, Feedback, UnknownState
from blackbase.evaluation import StateMaterializationResult, StateReleaseResult, StateTransitionResult
from blackbase.resources import ResourceContext
from blackbase.state_ref import StateRef
from nsgablack.adapters import (
    CompositeAdapter, DifferentialEvolutionAdapter, GradientOptimizerAdapter,
    MOEADAdapter, NSGA2Adapter, RoleAdapter,
)
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.representation import (
    DecompositionUnitBuilder, DifferentialPopulationBuilder, JointRepairPolicy,
    PopulationUnitBuilder, RepresentationPipeline,
)
from nsgablack.units import DecompositionUnit, DifferentialPopulationUnit, PopulationUnit, UnitBinding, UnitSchema
from nsgablack.project.scaffold.case_template_solver.pipeline.population_example import AgePopulationUnit
from tests.test_joint_repair_orchestration import Select


@dataclass
class RecordedPopulation(AgePopulationUnit):
    member_changes: list = field(default_factory=list)
    repair_marker: int = 0
    schema = UnitSchema("test.composition_population", required_fields=(
        *PopulationUnit.schema.required_fields, "age", "member_changes", "repair_marker"),
        candidate_projection=False)

    def on_members_changed(self, change):
        return {**super().on_members_changed(change), "member_changes": [
            *self.member_changes, dict(operation=change.operation,
                previous=list(change.previous_member_indices),
                incoming=list(change.incoming_member_indices), incoming_count=change.incoming_count),
        ]}


class RecordedBuilder(PopulationUnitBuilder):
    unit_type = RecordedPopulation
    compatible_schemas = (PopulationUnit.schema,)


@dataclass
class RecordedDifferential(DifferentialPopulationUnit, RecordedPopulation):
    schema = UnitSchema("test.composition_de", required_fields=(
        *DifferentialPopulationUnit.schema.required_fields, "age", "member_changes", "repair_marker"),
        candidate_projection=False)


class RecordedDifferentialBuilder(DifferentialPopulationBuilder):
    unit_type = RecordedDifferential
    compatible_schemas = (DifferentialPopulationUnit.schema,)


@dataclass
class RecordedDecomposition(DecompositionUnit, RecordedPopulation):
    schema = UnitSchema("test.composition_moead", required_fields=(
        *DecompositionUnit.schema.required_fields, "age", "member_changes", "repair_marker"),
        candidate_projection=False)


class RecordedDecompositionBuilder(DecompositionUnitBuilder):
    unit_type = RecordedDecomposition
    compatible_schemas = (DecompositionUnit.schema,)


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimize", "minimize"], bounds=[(0., 5.)])
        self.seen = []

    def evaluate(self, candidate):
        self.seen.append(np.array(candidate, copy=True))
        return [float(candidate[0]), float(candidate[0] ** 2)]


class CandidateOperator:
    def initialize(self, problem, context):
        return np.array([1.])

    def mutate(self, candidate, context):
        return np.array(candidate, copy=True)


class Bounds:
    def repair(self, candidate, context):
        if isinstance(candidate, UnknownState):
            return candidate.with_values(np.clip(candidate.values, 0., 5.))
        return np.clip(candidate, 0., 5.)

    def validate(self, candidate, context):
        return bool(np.all((candidate.values >= 0.) & (candidate.values <= 5.)))


class Repair:
    """Change candidate values and one persistent structural field, never select."""
    def __init__(self, owner):
        self.pending_fields = owner.admission_unit_fields
        self.repairs, self.projections = [], []

    def repair(self, unit, evidence, context):
        self.repairs.append(evidence)
        unit.repair_marker += 1
        return CandidateBatch.from_candidates(
            [state.with_values([0.125]) for state in evidence.after.semantic_states],
            candidate_tokens=evidence.after.candidate_tokens)

    def validate(self, unit, evidence, context):
        return bool(np.all(evidence.after.numeric_matrix == 0.125) and
            all(len(getattr(unit, name)) == len(evidence.proposal_indices) for name in self.pending_fields))

    def project_admission(self, baseline, draft, evidence, disposition, context):
        for name in self.pending_fields:
            assert len(getattr(baseline, name)) == evidence.proposed_count
            expected = [getattr(baseline, name)[i] for i in disposition.accepted_indices]
            np.testing.assert_array_equal(getattr(draft, name), expected)
        # Repair/projection must not count as an environmental selection.
        np.testing.assert_array_equal(draft.age, baseline.age)
        assert draft.member_changes == baseline.member_changes
        self.projections.append((evidence.proposal_indices, disposition.accepted_indices))
        return draft


def owner_for(algorithm, *, name=None):
    if algorithm == "nsga2":
        return NSGA2Adapter(name=name or algorithm, population_size=4, offspring_size=4,
                           unit_binding=UnitBinding(RecordedBuilder()))
    if algorithm == "de":
        return DifferentialEvolutionAdapter(name=name or algorithm, population_size=4, batch_size=4,
                           unit_binding=UnitBinding(RecordedDifferentialBuilder()))
    return MOEADAdapter(name=name or algorithm, population_size=4, batch_size=4,
                        neighborhood_size=4, weight_generation="random", variation="de",
                        unit_binding=UnitBinding(RecordedDecompositionBuilder()))


def control_for(owner):
    operator = CandidateOperator()
    control = ComposableSolver(Problem(), adapter=owner,
        representation_pipeline=RepresentationPipeline(initializer=operator, mutator=operator, repair=Bounds()))
    control.set_random_seed(14)
    return control


def prepare(algorithm, monkeypatch):
    owner = owner_for(algorithm)
    control = control_for(owner)
    control.setup()
    assert control.step().committed
    owner.algorithm_unit.age = np.array([10, 20, 30, 40])
    owner.algorithm_unit.member_changes = []
    repair = bind_repair(owner, monkeypatch)
    control.joint_repair_policy = JointRepairPolicy()
    control.evaluation_acceptance_policy = Select((1, 3))
    return control, owner, repair


def bind_repair(owner, monkeypatch):
    original = owner.propose
    def propose(control, context):
        rows = original(control, context)  # Keep the real algorithm's pending coordinates.
        return [UnknownState([2. + i * 0.1], {"owner": owner.name, "proposal_row": i})
                for i in range(len(rows))]
    monkeypatch.setattr(owner, "propose", propose)
    repair = Repair(owner)
    owner.set_unit_repair(repair)
    return repair


def assert_members(owner, repair, original_ages):
    tokens = repair.repairs[-1].after.candidate_tokens
    accepted_tokens = {tokens[1], tokens[3]}
    changes = owner.algorithm_unit.member_changes
    assert changes and all(row["operation"] in {"selection", "replacement"} for row in changes)
    expected = original_ages.copy()
    for change in changes:
        increment = int(change["operation"] == "selection")
        expected = np.array([0 if old is None else expected[old] + increment for old in change["previous"]])
        assert all(i is None or 0 <= i < change["incoming_count"] for i in change["incoming"])
    np.testing.assert_array_equal(owner.algorithm_unit.age, expected)
    final_tokens = owner.get_population_candidate_tokens()
    assert accepted_tokens.intersection(final_tokens)
    assert tokens[0] not in final_tokens and tokens[2] not in final_tokens
    assert repair.projections == [((0, 1, 2, 3), (1, 3))]
    assert len(repair.repairs) == 1
    assert owner.algorithm_unit.repair_marker == 1
    owner.algorithm_unit.require_current_feedback()


@pytest.mark.parametrize("algorithm", ["nsga2", "de", "moead"])
def test_joint_repair_nonprefix_admission_preserves_members_identity_and_destination(algorithm, monkeypatch):
    control, owner, repair = prepare(algorithm, monkeypatch)
    before = control.evaluation_count
    outcome = control.step()
    assert outcome.committed and control.evaluation_count - before == 4
    np.testing.assert_array_equal(control.problem.seen[-4:], [[0.125]] * 4)
    assert_members(owner, repair, np.array([10, 20, 30, 40]))
    if algorithm == "nsga2":
        # Original proposal rows 1/3 are now incoming rows 0/1 for this operation.
        change = owner.algorithm_unit.member_changes[0]
        assert change["incoming_count"] == 2
        assert {i for i in change["incoming"] if i is not None} == {0, 1}
    event = control._last_evaluated_event_batch
    assert [state.metadata["proposal_row"] for state in event.semantic_states] == [0, 1, 2, 3]
    batch = control.get_candidate_population_batch()
    for state, token in zip(batch.semantic_states, batch.candidate_tokens):
        if token in repair.repairs[0].after.candidate_tokens:
            assert state.metadata["proposal_row"] in {1, 3}
    destination = control.snapshot_store.read(control.population_authority.snapshot_handle.key)
    np.testing.assert_array_equal(destination.data["population"], owner.algorithm_unit.population)
    assert CandidateBatch.from_dict(destination.data["candidate_batch"]).as_dict() == batch.as_dict()
    record = control.evaluation_evidence_journal.get(outcome.metadata["evaluation_disposition"]["event_id"])
    assert record.terminal_verified and record.outcome == "accepted"


@pytest.mark.parametrize("algorithm", ["nsga2", "de", "moead"])
def test_failure_after_member_update_rolls_back_unit_and_authority_but_keeps_evidence(algorithm, monkeypatch):
    control, owner, repair = prepare(algorithm, monkeypatch)
    before = json.loads(json.dumps(owner.get_state()))
    authority = control.get_population_authority_identity()
    count = control.evaluation_count
    observed = []
    def fail(*args, **kwargs):
        assert_members(owner, repair, np.array([10, 20, 30, 40]))
        observed.append(True)
        raise RuntimeError("after member maintenance, before commit")
    monkeypatch.setattr(control, "_update_best", fail)
    with pytest.raises(RuntimeError, match="after member maintenance"):
        control.step()
    assert observed == [True] and owner.get_state() == before
    assert control.get_population_authority_identity() == authority
    assert control.pending_snapshot_step_key() is None
    assert control.evaluation_count - count == 4
    record = control.evaluation_evidence_journal.get(control._last_evaluation_event_id)
    assert record.terminal_verified and record.outcome == "execution_failed"
    assert control.snapshot_store.read(record.event_snapshot_key) is not None
    calls = (len(control.problem.seen), len(repair.repairs), len(repair.projections))
    control.reconcile_evaluation_evidence(run_id=record.run_id)
    assert calls == (len(control.problem.seen), len(repair.repairs), len(repair.projections))
    assert owner.get_state() == before


@pytest.mark.parametrize("algorithm", ["nsga2", "de", "moead"])
def test_zero_admission_discards_repair_and_does_not_maintain_members(algorithm, monkeypatch):
    control, owner, repair = prepare(algorithm, monkeypatch)
    before = owner.get_state()
    authority = control.get_population_authority_identity()
    count = control.evaluation_count
    control.evaluation_acceptance_policy = Select(())
    result = control.step()
    assert result.status == "rejected" and control.evaluation_count - count == 4
    after = owner.unit_binding.dump(owner.algorithm_unit)
    # Normal rejection consumes this proposal's pending coordinates. It must
    # preserve members/repair state, not reinstate a previous attempt's pending.
    for name in ("population", "objectives", "violations", "candidate_tokens",
                 "age", "member_changes", "repair_marker"):
        assert after["payload"][name] == before["algorithm_unit"]["payload"][name]
    assert all(len(getattr(owner.algorithm_unit, name)) == 0 for name in owner.admission_unit_fields)
    assert not owner.algorithm_unit.member_changes and not repair.projections
    assert control.get_population_authority_identity() == authority


@pytest.mark.parametrize("algorithm", ["nsga2", "de", "moead"])
def test_checkpoint_restores_composed_members_without_replaying_repair_or_maintenance(algorithm, monkeypatch, tmp_path):
    control, owner, repair = prepare(algorithm, monkeypatch)
    assert control.step().committed
    saved = json.loads(json.dumps(owner.get_state()))
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "unit-composition-test-key")
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path), save_on_finish=False)
    writer = CheckpointResumePlugin(config=config)
    control.add_plugin(writer)
    path = writer.save_checkpoint(reason="joint-repair-member-composition")
    assert path is not None
    target_owner = owner_for(algorithm)
    target = control_for(target_owner)
    target.joint_repair_policy = JointRepairPolicy()
    target.evaluation_acceptance_policy = Select((1, 3))
    target_repair = bind_repair(target_owner, monkeypatch)
    reader = CheckpointResumePlugin(config=config)
    target.add_plugin(reader)
    assert reader.resume(str(path))
    target.run(max_steps=0)
    assert target_owner.get_state()["algorithm_unit"] == saved["algorithm_unit"]
    assert not target_repair.repairs and not target_repair.projections
    assert not target.problem.seen
    np.testing.assert_array_equal(target.population_authority.population, owner.algorithm_unit.population)


def test_nested_same_type_owners_keep_local_coordinates_and_rejected_sibling_state(monkeypatch, tmp_path):
    left, right = owner_for("nsga2"), owner_for("nsga2")
    root = CompositeAdapter([RoleAdapter("left", left), RoleAdapter("right", right)])
    control = control_for(root)
    control.setup()
    assert control.step().committed
    assert left.algorithm_unit.unit_id == right.algorithm_unit.unit_id
    for owner in (left, right):
        owner.algorithm_unit.age = np.array([10, 20, 30, 40])
        owner.algorithm_unit.member_changes = []
    left_repair, right_repair = bind_repair(left, monkeypatch), bind_repair(right, monkeypatch)
    right_before = right.unit_binding.dump(right.algorithm_unit)
    control.joint_repair_policy = JointRepairPolicy()
    control.evaluation_acceptance_policy = Select((1, 3))
    assert control.step().committed
    assert_members(left, left_repair, np.array([10, 20, 30, 40]))
    assert right.unit_binding.dump(right.algorithm_unit) == right_before
    assert len(right_repair.repairs) == 1 and not right_repair.projections
    assert control.population_authority.mode == "partitioned"
    assert len(control.population_authority.partitions) == 2
    saved = [owner.unit_binding.dump(owner.algorithm_unit) for owner in (left, right)]
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "unit-composition-test-key")
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path), save_on_finish=False)
    writer = CheckpointResumePlugin(config=config)
    control.add_plugin(writer)
    path = writer.save_checkpoint(reason="same-unit-id-different-owner-path")
    restored_left, restored_right = owner_for("nsga2"), owner_for("nsga2")
    restored = control_for(CompositeAdapter([
        RoleAdapter("left", restored_left), RoleAdapter("right", restored_right)]))
    restored.joint_repair_policy = JointRepairPolicy()
    repairs = [bind_repair(owner, monkeypatch) for owner in (restored_left, restored_right)]
    reader = CheckpointResumePlugin(config=config)
    restored.add_plugin(reader)
    assert reader.resume(str(path))
    restored.run(max_steps=0)
    assert [owner.unit_binding.dump(owner.algorithm_unit) for owner in (restored_left, restored_right)] == saved
    assert not restored.problem.seen and all(not item.repairs for item in repairs)
    assert len(restored.population_authority.partitions) == 2


def test_budget_then_nonprefix_admission_keeps_original_and_member_coordinates_distinct(monkeypatch):
    control, owner, repair = prepare("nsga2", monkeypatch)
    monkeypatch.setattr(control, "evaluation_batch_allowance", lambda count, context=None: min(count, 3))
    control.evaluation_acceptance_policy = Select((1,))
    count = control.evaluation_count
    result = control.step()
    assert result.committed and control.evaluation_count - count == 3
    evidence = repair.repairs[0]
    assert evidence.proposed_count == 4 and evidence.proposal_indices == (0, 1, 2)
    assert repair.projections == [((0, 1, 2), (1,))]
    change = owner.algorithm_unit.member_changes[0]
    assert change["incoming_count"] == 1
    assert {i for i in change["incoming"] if i is not None} == {0}
    assert evidence.after.candidate_tokens[1] in owner.get_population_candidate_tokens()
    assert result.metadata["proposal_disposition"]["proposed_count"] == 4
    assert tuple(result.metadata["proposal_disposition"]["accepted_indices"]) == (1,)


class Gateway:
    """Deterministic Provider protocol double; it does not claim backend math."""
    def __init__(self):
        self.transitions, self.materializations, self.releases = [], [], []

    def transition(self, request, resource):
        self.transitions.append(request)
        attempt = len(self.transitions)
        slots = {name: StateRef(provider_id="composition-provider/v1",
            state_id=f"slot-{name}-{attempt}", state_kind=f"optimizer_slot.{name}",
            scope_id="composition", trajectory_id="gradient") for name in ("m", "v")}
        successor = StateRef(provider_id="composition-provider/v1", state_id=f"parameter-{attempt}",
            state_kind="model_parameters", scope_id="composition", trajectory_id="gradient")
        return StateTransitionResult(request_id=request.request_id, method_id=request.method_id,
            status="applied", state_ref=successor, slot_refs=slots)

    def materialize(self, request, resource):
        assert request.release_after
        self.materializations.append(request.state_ref.state_id)
        return StateMaterializationResult(request_id=request.request_id, state_ref=request.state_ref,
            target=request.target, value=UnknownState([0.5], {"provider": "composition"}))

    def release(self, request, resource):
        self.releases.append(request)
        return StateReleaseResult(request_id=request.request_id, provider_id=request.provider_id,
            status="released", released_count=len(request.state_ids), released_state_ids=request.state_ids)


class ProviderProblem(Problem):
    def evaluate(self, candidate):
        objectives = super().evaluate(candidate)
        return Feedback(objectives=objectives,
            gradient_ref=StateRef(provider_id="composition-provider/v1", state_id="gradient",
                state_kind="gradient", scope_id="composition", trajectory_id="gradient"),
            info={"constraint_violation": 0., "evaluation_state_ref": StateRef(
                provider_id="composition-provider/v1", state_id="parameters",
                state_kind="model_parameters", scope_id="composition", trajectory_id="gradient")})


@pytest.mark.parametrize("fail_before_commit", [False, True])
def test_member_repair_and_provider_cow_share_commit_and_failure_boundaries(fail_before_commit, monkeypatch):
    population, gateway = owner_for("nsga2"), Gateway()
    gradient = GradientOptimizerAdapter(name="gradient", state_gateway=gateway, prefer_provider_transition=True)
    root = CompositeAdapter([population, gradient])
    operator = CandidateOperator()
    control = ComposableSolver(ProviderProblem(), adapter=root,
        resource_context=ResourceContext(namespace="composition", grant={"threads": 1, "workers": 1}),
        representation_pipeline=RepresentationPipeline(initializer=operator, mutator=operator, repair=Bounds()))
    control.setup()
    assert control.step().committed
    population.algorithm_unit.age = np.array([10, 20, 30, 40])
    population.algorithm_unit.member_changes = []
    population_before = population.get_state()
    gradient_before = gradient.snapshot_step_state()
    slots_before = dict(gradient._provider_slot_refs)
    authority = control.get_population_authority_identity()
    before_evaluations = control.evaluation_count
    repair = bind_repair(population, monkeypatch)
    control.joint_repair_policy = JointRepairPolicy()
    control.evaluation_acceptance_policy = Select((1, 3, 4))
    original = control._update_best
    def after_updates(*args, **kwargs):
        assert_members(population, repair, np.array([10, 20, 30, 40]))
        assert len(gateway.transitions) == 2
        assert {ref.state_id for ref in gradient._provider_slot_refs.values()} == {"slot-m-2", "slot-v-2"}
        if fail_before_commit:
            raise RuntimeError("after population and Provider updates")
        return original(*args, **kwargs)
    monkeypatch.setattr(control, "_update_best", after_updates)
    if fail_before_commit:
        with pytest.raises(RuntimeError, match="population and Provider"):
            control.step()
        assert population.get_state() == population_before
        assert gradient.snapshot_step_state()["algorithm_unit"] == gradient_before["algorithm_unit"]
        assert gradient._provider_slot_refs == slots_before
        assert control.get_population_authority_identity() == authority
        expected_released = {"slot-m-2", "slot-v-2"}
    else:
        assert control.step().committed
        assert control.get_population_authority_identity() != authority
        expected_released = {"slot-m-1", "slot-v-1"}
    assert len(gateway.releases) == 1
    assert set(gateway.releases[0].state_ids) == expected_released
    assert gateway.materializations == ["parameter-1", "parameter-2"]
    assert control.evaluation_count - before_evaluations == 5
    record = control.evaluation_evidence_journal.get(control._last_evaluation_event_id)
    assert record.terminal_verified
    assert record.outcome == ("execution_failed" if fail_before_commit else "accepted")
