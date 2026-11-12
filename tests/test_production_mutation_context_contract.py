"""Production VNS inputs are declared and affect the real numeric proposals."""
import importlib
from pathlib import Path

import numpy as np

from blackbase.project import case_import_context
from nsgablack.context_keys import KEY_MUTATION_SIGMA, KEY_VNS_K


PROJECT = Path(__file__).resolve().parents[1] / "examples/cases/production_scheduling"


def _mutator():
    with case_import_context(PROJECT, "production_scheduling"):
        component = importlib.import_module("pipeline.schedule_pipeline").ProductionScheduleMutation
    return component(toggle_rate=0, per_gene_rate=.2)


def test_production_mutator_declares_its_optional_vns_inputs():
    operator = _mutator()
    assert operator.context_requires == ()
    assert set(operator.context_optional) == {KEY_MUTATION_SIGMA, KEY_VNS_K}


def test_vns_context_changes_real_proposals_and_replays_with_the_same_random_state():
    operator = _mutator()
    candidate = np.full(512, 1500.)
    saved_state = np.random.get_state()
    try:
        np.random.seed(1729)
        proposal_state = np.random.get_state()
        ordinary = operator.mutate(candidate, {})
        np.random.set_state(proposal_state)
        focused = operator.mutate(candidate, {KEY_MUTATION_SIGMA: 30., KEY_VNS_K: 3})
        np.random.set_state(proposal_state)
        replayed = operator.mutate(candidate, {KEY_MUTATION_SIGMA: 30., KEY_VNS_K: 3})
        np.testing.assert_array_equal(focused, replayed)
        assert not np.array_equal(ordinary, focused)
        assert np.abs(focused - candidate).sum() > np.abs(ordinary - candidate).sum()
        np.testing.assert_array_equal(candidate, np.full(512, 1500.))
    finally:
        np.random.set_state(saved_state)
