"""Only declared operator data is saved; locks and object graphs stay live."""
import copy
import numpy as np
import pytest

from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import GaussianMutation


def test_pipeline_rng_and_shared_operator_aliases_roundtrip_once():
    op = GaussianMutation(sigma=0.2)
    pipe = RepresentationPipeline(mutator=op, mutation_operators={"shared": op}, random_seed=42)
    before = copy.deepcopy(pipe.get_state())
    assert list(before["operators"]) == ["mutator"]
    assert before["identity"]["aliases"]["mutation_operators/shared"] == "mutator"
    expected = op.mutate(np.ones(5), {})
    own_random = pipe._rng.random()
    lock = pipe._lock
    pipe.set_state(before)
    np.testing.assert_array_equal(op.mutate(np.ones(5), {}), expected)
    assert pipe._rng.random() == own_random
    assert pipe._lock is lock


def test_changed_alias_layout_is_rejected_before_any_state_is_changed():
    op = GaussianMutation(sigma=0.2)
    source = RepresentationPipeline(mutator=op, mutation_operators={"shared": op}, random_seed=1)
    target = RepresentationPipeline(mutator=GaussianMutation(sigma=0.2),
        mutation_operators={"shared": GaussianMutation(sigma=0.2)}, random_seed=2)
    before = target.get_state()
    with pytest.raises(ValueError, match="alias layout"):
        target.set_state(source.get_state())
    assert target.get_state() == before


def test_declared_stateful_operator_without_a_codec_is_not_silently_skipped():
    class Stateful:
        stateless = False
        def mutate(self, candidate, context):
            return candidate
    pipe = RepresentationPipeline(mutator=Stateful())
    with pytest.raises(TypeError, match="no explicit state codec"):
        pipe.get_state()


def test_old_checkpoint_missing_a_stateful_pipeline_is_rejected(sample_problem):
    from nsgablack.core import ComposableSolver
    from nsgablack.plugins import CheckpointResumePlugin
    solver = ComposableSolver(sample_problem,
        representation_pipeline=RepresentationPipeline(mutator=GaussianMutation(sigma=0.2)))
    reader = CheckpointResumePlugin()
    with pytest.raises(ValueError, match="missing required component state: representation"):
        reader._apply_component_states(solver, {})
