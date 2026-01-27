import numpy as np

from nsgablack.representation.base import RepresentationPipeline


class InPlaceAddMutator:
    def __init__(self, delta: float = 1.0):
        self.delta = float(delta)

    def mutate(self, x, context=None):
        arr = np.asarray(x)
        arr += self.delta
        return arr


class RaisingRepair:
    def repair(self, x, context=None):
        raise RuntimeError("repair failed")


class IdentityRepair:
    def repair(self, x, context=None):
        return x


def test_transactional_mutate_rolls_back_on_repair_error():
    x = np.array([1.0, 2.0])
    pipeline = RepresentationPipeline(
        mutator=InPlaceAddMutator(10.0),
        repair=RaisingRepair(),
        transactional=True,
        protect_input=False,
    )

    y = pipeline.mutate(x, context={"generation": 0})

    # transactional=True 应保证返回原始输入，且原始输入不被原地改写
    assert np.allclose(y, np.array([1.0, 2.0]))
    assert np.allclose(x, np.array([1.0, 2.0]))


def test_protect_input_prevents_inplace_mutation():
    x = np.array([3.0, 4.0])
    pipeline = RepresentationPipeline(
        mutator=InPlaceAddMutator(5.0),
        repair=IdentityRepair(),
        transactional=False,
        protect_input=True,
    )

    y = pipeline.mutate(x)

    assert np.allclose(y, np.array([8.0, 9.0]))
    assert np.allclose(x, np.array([3.0, 4.0]))


def test_mutate_batch_falls_back_and_matches_per_item():
    xs = np.array([[0.0, 1.0], [2.0, 3.0], [4.0, 5.0]])
    pipeline = RepresentationPipeline(
        mutator=InPlaceAddMutator(2.0),
        repair=IdentityRepair(),
        protect_input=True,
    )

    ys_batch = np.asarray(pipeline.mutate_batch(xs))
    ys_loop = np.asarray([pipeline.mutate(x) for x in xs])

    assert ys_batch.shape == ys_loop.shape
    assert np.allclose(ys_batch, ys_loop)
