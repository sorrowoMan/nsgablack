import warnings

import numpy as np


def test_vns_adapter_warns_when_mutator_not_context_aware():
    from nsgablack.core.adapters import VNSAdapter
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
    from nsgablack.core.adapters import VNSAdapter
    from nsgablack.representation import RepresentationPipeline, ContextSwitchMutator

    class AddOne:
        def mutate(self, x, context=None):
            return np.asarray(x, dtype=float) + 1.0

    class StubSolver:
        def __init__(self):
            self.representation_pipeline = RepresentationPipeline(
                mutator=ContextSwitchMutator(mutators=[AddOne()], k_key="vns_k")
            )

    adapter = VNSAdapter()
    solver = StubSolver()

    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        adapter.setup(solver)
        assert len(rec) == 0

