"""The documented callable scoring and control-mapping roles stay distinct."""
import numpy as np
import pytest

from nsgablack.bias import BiasModule
from nsgablack.bias.domain.callable_bias import CallableBias
from nsgablack.bias.surrogate import SurrogateBiasContext, SurrogateControlBias, PhaseScheduleBias, UncertaintyBudgetBias


def test_plain_callable_registration_applies_weight_to_scalar_and_vector_without_mutating_raw():
    module = BiasModule()
    assert module.add(lambda candidate: float(candidate.sum()), weight=0.25, name="linear")
    candidate = np.array([1.0, 2.0])
    raw = np.array([10.0, 20.0])
    assert module.compute_bias(candidate, 10.0, context={}) == pytest.approx(10.75)
    selected = module.compute_bias_vector(candidate, raw, context={})
    assert selected == pytest.approx([10.75, 20.75])
    assert raw.tolist() == [10.0, 20.0]
    assert candidate.tolist() == [1.0, 2.0]


def test_callable_receives_actual_optimization_context_and_multiple_weights_accumulate():
    module = BiasModule()
    module.add(lambda candidate, context: float(context.generation), weight=0.5, name="generation")
    module.add(lambda candidate: 2.0, weight=0.25, name="constant")
    assert module.compute_bias(np.array([1.0]), 10.0, context={"generation": 4}) == pytest.approx(12.5)


def test_explicit_reward_callable_remains_negative_selection_delta():
    module = BiasModule()
    module.add(CallableBias("reward", lambda candidate: 2.0, weight=0.5, mode="reward"))
    assert module.compute_bias(np.array([1.0]), 10.0, context={}) == pytest.approx(9.0)


def control_context():
    return SurrogateBiasContext(generation=5, max_generations=10, population=None,
        surrogate_manager=None, surrogate_ready=False, n_training_samples=0,
        model_quality={}, real_eval_count=0, surrogate_eval_count=0,
        prefilter={}, score_bias={}, surrogate_eval={}, constraint_eval={})


@pytest.mark.parametrize("policy,expected", [
    (SurrogateControlBias(), {}),
    (PhaseScheduleBias([{"start": 0.0, "end": 1.0, "updates": {"prefilter": {"enabled": True, "ratio": 1.0}}}]),
     {"prefilter": {"enabled": True, "ratio": 1.0}}),
    (UncertaintyBudgetBias(), {"prefilter": {"enabled": True, "ratio": 1.0}}),
])
def test_control_components_produce_mapping_but_are_rejected_by_scalar_scoring(policy, expected):
    assert policy.apply(control_context()) == expected
    with pytest.raises(TypeError, match="control updates"):
        BiasModule().add(policy)
