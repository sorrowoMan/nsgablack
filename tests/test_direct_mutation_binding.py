"""Direct algorithm operators use existing Unit, provenance and repair seams."""
import copy
import threading

import numpy as np
import pytest
from blackbase.types import UnknownState

from nsgablack.adapters import AlgorithmAdapter
from nsgablack.adapters.operator_binding import OperatorBinding
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import GaussianMutation
from nsgablack.units import FeatureContractError, PopulationUnit, UnitInputSpec


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimize"], bounds=[(-100, 100)])
        self.seen = []

    def evaluate(self, candidate):
        self.seen.append(np.asarray(candidate).copy())
        return [float(candidate[0])]


class Shift:
    stateless = True

    def __init__(self, amount=1.0):
        self.amount = amount

    def checkpoint_identity(self):
        return {"amount": self.amount}

    def mutate(self, candidate, context=None):
        return candidate + self.amount


class DirectProbe(AlgorithmAdapter):
    uses_pipeline_mutation = True

    def __init__(self, mutator):
        super().__init__(name="direct_probe")
        self.mutator = mutator
        self.algorithm_unit = PopulationUnit("population", np.array([[2.0], [4.0]]))

    def get_bound_mutator(self):
        return self.mutator

    def propose(self, control, context):
        return [self.mutate_candidate(control, np.zeros(1), context)]

    def update(self, control, candidates, feedback, context):
        pass


def solver_for(mutator=None, pipeline=None):
    return ComposableSolver(Problem(), adapter=DirectProbe(mutator), representation_pipeline=pipeline)


@pytest.mark.parametrize("kind", ["no_context", "positional", "keyword"])
def test_direct_control_supports_declared_call_shapes_once(kind):
    calls = []
    class Mutator:
        pass
    def no_context(candidate):
        calls.append(kind)
        candidate[:] += 3
        return candidate
    def positional(candidate, context):
        assert context == {"offset": 3}
        return no_context(candidate)
    def keyword(candidate, *, context):
        assert context == {"offset": 3}
        return no_context(candidate)
    mutator = Mutator()
    mutator.mutate = {"no_context": no_context, "positional": positional, "keyword": keyword}[kind]
    parent = np.array([1.0])
    solver = solver_for(pipeline=RepresentationPipeline(mutator=Shift(100)))
    result = solver.mutate_candidate(parent, {"offset": 3}, mutator=mutator)
    np.testing.assert_array_equal(result, [4.0])
    np.testing.assert_array_equal(parent, [1.0])
    assert calls == [kind]
    old, new = solver.candidate_provenance_for(parent), solver.candidate_provenance_for(result)
    assert new.candidate_token != old.candidate_token and new.parent_token == old.candidate_token
    refs = solver.solution_pool.select(stage="mutation")
    assert tuple(ref.candidate_token for ref in refs) == (new.candidate_token,)
    np.testing.assert_array_equal(solver.solution_pool.read(refs).numeric_matrix, [[4.0]])


def test_direct_semantic_mutation_keeps_metadata_and_derives_identity():
    class Semantic:
        def mutate(self, candidate):
            assert isinstance(candidate, UnknownState)
            return candidate.with_values(candidate.as_array() + 1)
    solver = solver_for()
    parent = UnknownState([2.0], {"source": "domain"})
    result = solver.mutate_candidate(parent, mutator=Semantic())
    assert isinstance(result, UnknownState) and result.metadata["source"] == "domain"
    np.testing.assert_array_equal(result.as_array(), [3.0])
    assert solver.candidate_provenance_for(result).parent_token == solver.candidate_provenance_for(parent).candidate_token


def test_direct_callback_typeerror_is_not_retried_or_fallen_back():
    calls = []
    class Failing:
        def mutate(self, candidate, context=None):
            calls.append("direct")
            raise TypeError("operator body failed")
    solver = solver_for(pipeline=RepresentationPipeline(mutator=Shift(100)))
    with pytest.raises(TypeError, match="operator body failed"):
        solver.mutate_candidate(np.zeros(1), mutator=Failing())
    assert calls == ["direct"]


def test_direct_and_named_bindings_are_unambiguous_and_legacy_is_preserved():
    pipeline = RepresentationPipeline(mutator=Shift(2), mutation_operators={"named": Shift(7)})
    solver = solver_for(Shift(4), pipeline)
    assert solver.adapter.get_mutation_operator(solver).amount == 4
    with pytest.raises(ValueError, match="both be bound"):
        solver.adapter.set_mutation_operator("named")
    with pytest.raises(ValueError, match="mutually exclusive"):
        solver.mutate_candidate(np.zeros(1), operator="named", mutator=Shift(4))
    legacy = solver_for(pipeline=pipeline)
    legacy.adapter.set_mutation_operator("named")
    np.testing.assert_array_equal(legacy.adapter.mutate_candidate(legacy, np.zeros(1), {}), [7.0])
    legacy.adapter.set_mutation_operator(None)
    np.testing.assert_array_equal(legacy.adapter.mutate_candidate(legacy, np.zeros(1), {}), [2.0])


def test_direct_unit_dependency_is_captured_readonly_and_repair_runs_once():
    captures, repairs = [], []
    class PopulationMutation:
        unit_inputs = UnitInputSpec(fields=("population",))
        def mutate(self, candidate, context, *, unit):
            with pytest.raises(ValueError, match="read-only"):
                unit.fields["population"][0, 0] = 50
            captures.append(unit)
            return unit.fields["population"].mean(axis=0).copy()
    class Repair:
        def repair(self, candidate, context=None):
            repairs.append(np.asarray(candidate).copy())
            return candidate + 10
    solver = solver_for(PopulationMutation(), RepresentationPipeline(repair=Repair()))
    draft = solver.adapter.mutate_candidate(solver, np.zeros(1), {})
    assert not repairs
    np.testing.assert_array_equal(draft, [3.0])
    assert solver.step().committed
    assert len(repairs) == 1
    np.testing.assert_array_equal(solver.problem.seen, [[13.0]])
    solver.adapter.algorithm_unit.population[0, 0] = 20
    assert captures[0].fields["population"][0, 0] == 2


def test_direct_unit_contract_errors_happen_before_operator_execution():
    class NeedsUnit:
        unit_inputs = UnitInputSpec(fields=("population",))
        def mutate(self, candidate, context, *, unit):
            pytest.fail("invalid dependency executed")
    solver = solver_for()
    with pytest.raises(FeatureContractError, match="UnitInputs"):
        solver.mutate_candidate(np.zeros(1), mutator=NeedsUnit())
    unit = NeedsUnit.unit_inputs.capture(PopulationUnit("p", np.ones((2, 1))))
    with pytest.raises(ValueError, match="did not declare"):
        solver.mutate_candidate(np.zeros(1), mutator=Shift(), unit=unit)
    class BadSignature(NeedsUnit):
        def mutate(self, candidate):
            pytest.fail("invalid signature executed")
    with pytest.raises(TypeError, match="must accept"):
        solver.mutate_candidate(np.zeros(1), mutator=BadSignature(), unit=unit)
    class BadDeclaration(NeedsUnit):
        unit_inputs = {"fields": ["population"]}
    with pytest.raises(TypeError, match="must be UnitInputSpec"):
        solver.mutate_candidate(np.zeros(1), mutator=BadDeclaration(), unit=unit)


def test_binding_restores_gaussian_rng_and_checks_configuration_identity():
    operator = GaussianMutation(sigma=0.3, low=-5.0, high=5.0)
    binding = OperatorBinding(operator, method="mutate")
    binding.seed(42)
    state = binding.get_state()
    first = operator.mutate(np.zeros(4))
    binding.set_state(state)
    np.testing.assert_array_equal(operator.mutate(np.zeros(4)), first)
    clone = OperatorBinding(GaussianMutation(sigma=0.3, low=-5.0, high=5.0), method="mutate")
    clone.set_state(state)
    np.testing.assert_array_equal(clone.component.mutate(np.zeros(4)), first)
    other = OperatorBinding(GaussianMutation(sigma=0.9, low=-5.0, high=5.0), method="mutate")
    before = other.get_state()
    with pytest.raises(ValueError, match="identity"):
        other.set_state(state)
    assert other.get_state() == before
    assert "state" not in binding.describe()
    description = binding.describe()
    description["identity"]["sigma"] = 100
    assert binding.describe()["identity"]["sigma"] == 0.3


class CounterOperator:
    def __init__(self):
        self.values = [0]
        self.restores = 0
    def mutate(self, candidate, context=None):
        self.values[0] += 1
        return candidate
    def checkpoint_identity(self):
        return {"kind": "counter"}
    def get_state(self):
        return {"values": self.values}
    def set_state(self, state):
        self.restores += 1
        self.values = state["values"]


def test_binding_detaches_codec_values_and_preflight_never_restores():
    operator = CounterOperator()
    binding = OperatorBinding(operator, method="mutate")
    binding.seed(8)  # Deterministic stateful components need not own an RNG.
    state = binding.get_state()
    state["state"]["values"][0] = 7
    assert operator.values == [0]
    binding.validate_state(state)
    assert operator.restores == 0
    binding.set_state(state)
    state["state"]["values"][0] = 9
    assert operator.values == [7]
    invalid = copy.deepcopy(state)
    invalid["method"] = "select"
    with pytest.raises(ValueError, match="identity"):
        binding.validate_state(invalid)
    assert operator.restores == 1


def test_stateless_binding_requires_identity_but_no_mutable_codec():
    binding = OperatorBinding(Shift(2), method="mutate")
    assert binding.stateless and binding.component.amount == 2
    binding.set_state(binding.get_state())
    state = binding.get_state()
    state["state"]["hidden"] = 1
    with pytest.raises(ValueError, match="stateless"):
        binding.set_state(state)
    with pytest.raises(AttributeError):
        binding.component = Shift(3)
    class MissingIdentity:
        stateless = True
        mutate = Shift.mutate
    with pytest.raises(TypeError, match="checkpoint_identity"):
        OperatorBinding(MissingIdentity(), method="mutate")


@pytest.mark.parametrize("payload", [None, object(), threading.RLock(), np.array([object()], dtype=object)])
def test_binding_rejects_nonmapping_or_live_codec_payloads(payload):
    class Unsafe(CounterOperator):
        def get_state(self):
            return payload if payload is None else {"value": payload}
    with pytest.raises(TypeError):
        OperatorBinding(Unsafe(), method="mutate")


def test_binding_rejects_cycles_and_stateful_components_without_codec():
    class Cyclic(CounterOperator):
        def get_state(self):
            state = {}
            state["self"] = state
            return state
    with pytest.raises(TypeError, match="cyclic"):
        OperatorBinding(Cyclic(), method="mutate")
    class NoCodec:
        checkpoint_identity = CounterOperator.checkpoint_identity
        mutate = Shift.mutate
    with pytest.raises(TypeError, match="get_state"):
        OperatorBinding(NoCodec(), method="mutate")
