"""The small function surface must preserve the existing ownership boundary."""
from functools import partial

import numpy as np
import pytest

from nsgablack.adapters import ChangeRequest, NSGA2Adapter, VNSAdapter
from nsgablack.adapters.change import OrdinaryFunctionChange
from nsgablack.adapters.operator_binding import OperatorBinding
from nsgablack.utils.extension_contracts import inspect_adapter_operator_bindings
from numpy import sqrt as direct_sqrt


def offset(request, *, rng, amount=0.25):
    return request.candidate + amount + rng.normal(0, 0.001, request.candidate.shape)


def must_not_execute(request, *, rng):
    raise AssertionError("inspection executed the user's change function")


def sqrt_change(request, *, rng):
    return direct_sqrt(request.candidate)


def shift_helper(candidate):
    return candidate + 1


def composed_change(request, *, rng):
    return shift_helper(request.candidate)


def test_request_is_detached_readonly_and_does_not_expose_context_services():
    parents = np.array([[1., 2.], [3., 4.]])
    weights = np.array([0.2, 0.8])
    request = ChangeRequest(parents, parameters={"weight": weights, "nested": {"k": [1, 2]}},
                            context={"phase": "search", "solver": object(), "history": parents})
    parents[:] = 99
    weights[:] = 99
    np.testing.assert_array_equal(request.parents, [[1., 2.], [3., 4.]])
    np.testing.assert_array_equal(request.parameters["weight"], [0.2, 0.8])
    assert dict(request.context) == {"phase": "search"}
    assert request.parameters["nested"]["k"] == (1, 2)
    with pytest.raises(ValueError):
        request.parents.setflags(write=True)
    with pytest.raises(ValueError):
        request.parameters["weight"].setflags(write=True)
    with pytest.raises(TypeError):
        request.parameters["nested"]["new"] = 1


@pytest.mark.parametrize("parents", [[], [1., 2.], np.zeros((2, 0)), [[object()]]])
def test_parent_contract_rejects_missing_rows_or_non_numeric_objects(parents):
    with pytest.raises(ValueError, match="parents"):
        ChangeRequest(parents)


def test_plain_function_needs_no_user_component_methods_and_rng_is_supplied():
    component = OrdinaryFunctionChange(offset)
    request = ChangeRequest([[1., 2.]])
    first = component.change(request, rng=np.random.default_rng(17))
    second = component.change(request, rng=np.random.default_rng(17))
    np.testing.assert_array_equal(first, second)
    assert component.stateless
    binding = OperatorBinding(component, method="change")
    assert binding.get_state()["state"] == {}


def test_direct_numpy_import_is_an_external_function_not_hidden_mutable_state():
    np.testing.assert_array_equal(OrdinaryFunctionChange(sqrt_change).change(
        ChangeRequest([[1., 4.]]), rng=np.random.default_rng(1)), [1., 2.])


def test_partial_configuration_is_part_of_checkpoint_identity():
    first = OperatorBinding(OrdinaryFunctionChange(partial(offset, amount=1.)), method="change")
    second = OperatorBinding(OrdinaryFunctionChange(partial(offset, amount=2.)), method="change")
    with pytest.raises(ValueError, match="identity"):
        second.set_state(first.get_state())


def test_editing_a_direct_helper_invalidates_existing_binding_identity(monkeypatch):
    binding = OperatorBinding(OrdinaryFunctionChange(composed_change), method="change")
    monkeypatch.setitem(composed_change.__globals__, "shift_helper", lambda candidate: candidate + 2)
    with pytest.raises(ValueError, match="identity changed"):
        binding.get_state()


def test_immutable_closure_configuration_is_supported_but_hidden_mutable_state_is_not():
    amount = 0.5

    def configured(request, *, rng):
        return request.candidate + amount

    state = []

    def hidden_state(request, *, rng):
        state.append(1)
        return request.candidate

    np.testing.assert_array_equal(OrdinaryFunctionChange(configured).change(
        ChangeRequest([[1.]]), rng=np.random.default_rng(1)), [1.5])
    with pytest.raises(TypeError, match="mutable"):
        OrdinaryFunctionChange(hidden_state)


def test_bad_signature_and_async_functions_fail_at_assembly():
    def missing_rng(request):
        return request.candidate

    async def asynchronous(request, *, rng):
        return request.candidate

    with pytest.raises(TypeError):
        OrdinaryFunctionChange(missing_rng)
    with pytest.raises(TypeError, match="synchronously"):
        OrdinaryFunctionChange(asynchronous)


def test_inspection_does_not_call_user_function_and_unsupported_adapter_rejects_binding():
    adapter = VNSAdapter(change=must_not_execute)
    assert inspect_adapter_operator_bindings(adapter) == ()
    assert "change" in adapter.get_operation_contract()["variation"]
    with pytest.raises(ValueError, match="unsupported"):
        from nsgablack.adapters import DifferentialEvolutionAdapter
        DifferentialEvolutionAdapter().set_change(offset)


def test_typeerror_from_function_is_not_retried():
    def failed(request, *, rng):
        raise TypeError("calculation failed")

    with pytest.raises(TypeError, match="calculation failed"):
        OrdinaryFunctionChange(failed).change(ChangeRequest([[1.]]), rng=np.random.default_rng(1))
