"""结构 benchmark 必须使用独立参考并经过正式 Case 配对。"""
import json

import numpy as np
import pytest

from benchmarks import transparency_structured as structured


@pytest.mark.parametrize("name", structured.ALGORITHMS)
def test_reference_uses_injected_evaluations_without_algorithm_objects(name, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("bare reference must not build a framework Adapter")
    monkeypatch.setattr(structured, "make_adapter", forbidden)
    calls = []
    def evaluate(x):
        calls.append(np.asarray(x).tolist())
        return structured.objective(name, x), 0.
    result = structured.run_bare(name, seed=11, steps=6, evaluate=evaluate)
    assert result["evaluations"] == len(calls) == sum(map(len, result["batches"]))
    assert result["steps"] == len(result["trace"]) == 6
    assert result["shared_algorithm_components"] == []
    json.dumps(result, allow_nan=False)
    json.dumps(structured.metadata(name), allow_nan=False)


def test_moa_fixture_exercises_dominance_replacement_and_incomparable_paths():
    result = structured.run_bare("moa_star", seed=11, steps=6)
    initial = next(label for label in result["states"][2]["labels"] if label["state"] == [4.])
    replacement = next(label for label in result["states"][3]["labels"] if label["state"] == [4.])
    assert np.all(np.asarray(replacement["g"]) < initial["g"])
    alternatives = [label for label in result["state"]["labels"] if label["state"] == [6.]]
    assert len(alternatives) == 2
    a, b = [np.asarray(label["g"]) for label in alternatives]
    assert np.any(a < b) and np.any(b < a)


@pytest.mark.parametrize("name", structured.ALGORITHMS)
def test_structured_pair_matches_real_case_and_recovers(name):
    from benchmarks.transparency_core import run_pair
    spec = next(spec for spec in structured.specs() if spec.name == name)
    result = run_pair(spec, seed=11, recovery=True)
    assert result["semantics"]["status"] == "passed", result
    assert result["overhead"]["status"] == "measured", result
    assert result["recovery"]["status"] == "passed", result
