import warnings

import numpy as np
import pytest


def test_vns_adapter_warns_when_mutator_not_context_aware():
    from nsgablack.adapters import VNSAdapter
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import GaussianMutation

    class StubSolver:
        def __init__(self):
            self.representation_pipeline = RepresentationPipeline(mutator=GaussianMutation(sigma=0.1))

    adapter = VNSAdapter()
    solver = StubSolver()

    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        adapter.setup(solver)
        assert any("VNSAdapter" in str(w.message) for w in rec)


def test_vns_adapter_no_warn_for_context_aware_mutator():
    from nsgablack.adapters import VNSAdapter
    from nsgablack.representation import RepresentationPipeline, ContextSelectMutator

    class AddOne:
        def mutate(self, x, context=None):
            return np.asarray(x, dtype=float) + 1.0

    class StubSolver:
        def __init__(self):
            self.representation_pipeline = RepresentationPipeline(
                mutator=ContextSelectMutator(mutators=[AddOne()], k_key="vns_k")
            )

    adapter = VNSAdapter()
    solver = StubSolver()

    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        adapter.setup(solver)
        assert len(rec) == 0


@pytest.mark.parametrize(
    "default_aware,selected_aware,expected_warning",
    [(False, True, False), (True, False, True), (None, True, False)],
)
def test_vns_warning_follows_selected_named_mutator(default_aware, selected_aware, expected_warning):
    from types import SimpleNamespace

    from nsgablack.adapters import VNSAdapter
    from nsgablack.representation import RepresentationPipeline

    class Operator:
        def __init__(self, aware):
            self.context_requires = ("vns_k",) if aware else ()

        def mutate(self, candidate, context=None):
            return np.asarray(candidate, dtype=float) + 1.0

    default = None if default_aware is None else Operator(default_aware)
    selected = Operator(selected_aware)
    pipeline = RepresentationPipeline(mutator=default, mutation_operators={"local": selected})
    adapter = VNSAdapter()
    adapter.set_mutation_operator("local")
    solver = SimpleNamespace(representation_pipeline=pipeline)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        adapter.setup(solver)
    diagnostics = [item for item in captured if "VNSAdapter" in str(item.message)]
    assert bool(diagnostics) is expected_warning
    assert pipeline.mutator is default
    assert adapter.get_mutation_operator(solver) is selected


def test_vns_warning_rejects_unknown_named_mutator_instead_of_inspecting_default():
    from types import SimpleNamespace

    from nsgablack.adapters import VNSAdapter
    from nsgablack.representation import ContextGaussianMutation, RepresentationPipeline

    solver = SimpleNamespace(representation_pipeline=RepresentationPipeline(
        mutator=ContextGaussianMutation(base_sigma=0.1)))
    adapter = VNSAdapter()
    adapter.set_mutation_operator("missing")
    with pytest.raises(ValueError, match="unknown mutation operator"):
        adapter.setup(solver)


