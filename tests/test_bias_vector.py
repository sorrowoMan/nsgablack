import numpy as np

from nsgablack.bias import BiasModule
from nsgablack.bias.domain import CallableBias


def test_compute_bias_vector_matches_scalar_calls():
    bias = BiasModule()

    def penalty(x, constraints, context):
        # simple penalty based on x sum
        return {"penalty": float(np.sum(x))}

    def reward(x, constraints, context):
        # simple reward based on first coordinate
        return {"reward": float(np.asarray(x)[0])}

    bias.add(CallableBias(name="p", func=penalty, weight=2.0, mode="penalty"))
    bias.add(CallableBias(name="r", func=reward, weight=0.5, mode="reward"))

    x = np.array([3.0, 4.0])
    ctx = {"constraints": [], "generation": 1, "constraint_violation": 0.0}
    objectives = np.array([10.0, 20.0, 30.0])

    vec = bias.compute_bias_vector(x, objectives, individual_id=7, context=ctx)
    scalars = np.array([bias.compute_bias(x, float(v), 7, context=ctx) for v in objectives])

    assert np.allclose(vec, scalars)


def test_compute_bias_batch_shapes():
    bias = BiasModule()
    xs = np.array([[1.0, 2.0], [3.0, 4.0]])
    objectives = np.array([[5.0, 6.0], [7.0, 8.0]])
    contexts = [
        {"constraints": [], "generation": 0, "constraint_violation": 0.0},
        {"constraints": [], "generation": 0, "constraint_violation": 0.0},
    ]

    out = bias.compute_bias_batch(xs, objectives, contexts=contexts)
    assert out.shape == objectives.shape
