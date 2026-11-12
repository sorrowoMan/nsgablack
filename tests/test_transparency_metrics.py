"""指标必须来自 pymoo，且两条路径共享固定的参考文件与参考点。"""
import json
import shutil

import numpy as np
import pytest

pytest.importorskip("pymoo")

from benchmarks.transparency_metrics import REFERENCE_ROOT, load_reference, measure, quality


@pytest.mark.parametrize("problem", ["zdt1", "dtlz2"])
def test_measure_delegates_to_official_indicators_and_reference_file(problem, monkeypatch):
    from pymoo.indicators.hv import HV
    from pymoo.indicators.igd import IGD

    reference, source = load_reference(problem)
    values = reference[::50] * 1.1
    expected_hv = float(HV(ref_point=np.asarray(source["hv_reference_point"])).do(values))
    expected_igd = float(IGD(reference).do(values))
    calls = []
    hv_do, igd_do = HV.do, IGD.do

    def hv(self, values, *args, **kwargs):
        calls.append("HV")
        return hv_do(self, values, *args, **kwargs)

    def igd(self, values, *args, **kwargs):
        calls.append("IGD")
        return igd_do(self, values, *args, **kwargs)

    monkeypatch.setattr(HV, "do", hv)
    monkeypatch.setattr(IGD, "do", igd)
    actual = measure(problem, values, np.zeros(len(values)))
    assert calls == ["HV", "IGD"]
    assert actual["hv"] == pytest.approx(expected_hv, abs=1e-12)
    assert actual["igd"] == pytest.approx(expected_igd, abs=1e-12)
    assert actual["reference"]["sha256"] == source["sha256"]


def test_reference_tampering_is_rejected(tmp_path):
    root = tmp_path / "references"
    shutil.copytree(REFERENCE_ROOT, root)
    with (root / "zdt1.pf").open("a", encoding="utf-8") as stream:
        stream.write("0 0\n")
    with pytest.raises(ValueError, match="checksum"):
        load_reference("zdt1", root=root)


def test_metric_does_not_count_infeasible_candidates():
    values = np.asarray([[0.1, 0.1], [0.5, 0.8]])
    result = measure("zdt1", values, [10.0, 0.0])
    accepted_only = measure("zdt1", values[1:], [0.0])
    assert result["hv"] == accepted_only["hv"]
    assert result["igd"] == accepted_only["igd"]
    assert result["feasible_members"] == 1
    assert measure("zdt1", values, [1.0, 2.0])["igd"] is None


@pytest.mark.parametrize("problem", ["zdt1", "dtlz2"])
def test_reference_files_are_reproducible_outputs_of_official_generator(problem):
    from pymoo.problems import get_problem
    from pymoo.util.ref_dirs import get_reference_directions

    actual, source = load_reference(problem)
    official = get_problem(problem, **source["problem_arguments"])
    options = source["front_arguments"]
    if "reference_directions" in options:
        args = options["reference_directions"]
        options = {"ref_dirs": get_reference_directions(args["method"], args["n_dim"], n_partitions=args["n_partitions"])}
    np.testing.assert_array_equal(actual, official.pareto_front(**options))


def test_quality_detects_different_final_front_despite_equal_evaluation_history():
    from types import SimpleNamespace

    spec = SimpleNamespace(metric_problem="zdt1")
    left = {"objectives": [[0.2, 0.7]], "violations": [0.0]}
    right = {"objectives": [[0.4, 0.9]], "violations": [0.0]}
    result = quality(spec, {"state": left}, right, [], [])
    assert result["raw_objectives_equal"]
    assert result["status"] == "failed"
    assert result["deltas"]["hv"] != 0.0


def test_metric_rejects_unaligned_final_members():
    with pytest.raises(ValueError, match="aligned"):
        measure("zdt1", [[0.2, 0.7]], [])


def test_reference_preparation_reproduces_exact_bytes_without_platform_newline_conversion(tmp_path):
    from benchmarks.prepare_transparency_references import prepare

    generated = prepare(tmp_path)
    for name in ("zdt1", "dtlz2"):
        entry = generated["sets"][name]
        assert (tmp_path / entry["file"]).read_bytes() == (REFERENCE_ROOT / entry["file"]).read_bytes()
