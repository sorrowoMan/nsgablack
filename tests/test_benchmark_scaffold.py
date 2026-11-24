"""Verify the benchmark suites dispatch through the standard scaffold Case.

The full Project run also exercises BlackBase artifact publishing, which uses a
Windows tempfile path that is environment-sensitive; these tests verify the mode
dispatch and config plumbing directly with a mocked Case runtime.
"""
from types import SimpleNamespace

import numpy as np

from benchmarks.transparency_case import TransparencyCase, make_benchmark_case


def _fake_runtime():
    return SimpleNamespace(
        identity=SimpleNamespace(case_run_id="test:1",
                                 as_dict=lambda: {"case_run_id": "test:1"}),
        checkpoint=lambda: None,
        publish_artifact=lambda *a, **k: SimpleNamespace(as_dict=lambda: {"kind": "benchmark"}),
        request=SimpleNamespace(project_name="algorithm_transparency"),
    )


def test_component_overrides_override_mode():
    case = make_benchmark_case("matrix", mode="matrix", config={},
                               component_overrides={"config": {"mode": "quality"}})
    assert case.options["mode"] == "quality"


def test_quality_mode_dispatches():
    case = TransparencyCase("matrix", {
        "mode": "quality", "problems": ["zdt1"], "algorithms": ["nsga2"],
        "seeds": [11], "population_size": 20, "steps": 8,
    }, None)
    case.case_runtime = _fake_runtime()
    report = case._run()
    assert report["results"][0]["problem"] == "zdt1"
    assert report["results"][0]["algorithm"] == "nsga2"
    assert np.isfinite(report["results"][0]["igd"]["median"])


def test_single_objective_mode_dispatches():
    case = TransparencyCase("matrix", {
        "mode": "single_objective", "problems": ["sphere"], "seeds": [11],
        "n_var": 5, "steps": 10,
    }, None)
    case.case_runtime = _fake_runtime()
    report = case._run()
    assert report["results"][0]["problem"] == "sphere"
    assert report["results"][0]["best"]["median"] < 50.0


def test_fusion_mode_dispatches():
    case = TransparencyCase("matrix", {
        "mode": "fusion", "pairs": [["nsga2", "spea2"]], "problems": ["zdt1"],
        "seeds": [11], "population_size": 20, "total_steps": 8,
    }, None)
    case.case_runtime = _fake_runtime()
    report = case._run()
    assert report["results"][0]["pair"] == "nsga2->spea2"
    assert np.isfinite(report["results"][0]["hybrid_igd"]["median"])
