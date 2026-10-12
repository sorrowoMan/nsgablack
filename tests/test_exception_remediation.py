from types import SimpleNamespace

import pytest

from blackbase.project import collect_failure_evidence
from blackbase.representation import RepresentationCapabilities
from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter
from nsgablack.adapters.serial_strategy.adapter import StrategyChainAdapter, SerialPhaseSpec
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.plugins.system.checkpoint_resume import CheckpointResumePlugin


def test_declared_initializer_failure_never_silently_uses_random_candidate(sample_problem):
    class Pipeline:
        representation_capabilities = RepresentationCapabilities(frozenset({"init"}))
        def init(self, context):
            raise RuntimeError("domain initializer failed")

    solver = ComposableSolver(sample_problem, representation_pipeline=Pipeline())
    with pytest.raises(RuntimeError, match="domain initializer failed"):
        solver.init_candidate()
    assert solver.evaluation_count == 0
    assert solver.population is None


def test_checkpoint_never_returns_live_reference_when_detaching_fails():
    class LiveSession:
        def __deepcopy__(self, memo):
            raise TypeError("live provider cannot be copied")

    with pytest.raises(TypeError, match="live provider cannot be copied"):
        CheckpointResumePlugin()._safe_copy({"session": LiveSession()})


def test_checkpoint_cannot_omit_adapter_whose_state_capture_failed():
    class Broken:
        def get_state(self):
            raise RuntimeError("state capture failed")

    with pytest.raises(RuntimeError, match="state capture failed"):
        CheckpointResumePlugin()._collect_adapter_state(SimpleNamespace(adapter=Broken()))


def test_serial_teardown_attempts_every_child_after_failure():
    events = []

    class Child(AlgorithmAdapter):
        def propose(self, control, context):
            return ()
        def update(self, control, candidates, feedback, context):
            pass
        def teardown(self, control):
            events.append(self.name)
            raise RuntimeError(f"{self.name} failed")

    chain = StrategyChainAdapter(phases=[SerialPhaseSpec("a", Child(name="a")),
                                        SerialPhaseSpec("b", Child(name="b"))])
    chain.setup(SimpleNamespace())
    with pytest.raises(RuntimeError, match="a failed") as captured:
        chain.teardown(SimpleNamespace())
    assert events == ["a", "b"]
    assert len(collect_failure_evidence(captured.value)["serial_adapter_teardown"]) == 2
