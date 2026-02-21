from pathlib import Path

from benchmarks.fixed_baseline_runner import BaselineScenario, run_baseline


def test_fixed_baseline_runner_smoke(tmp_path: Path):
    report = run_baseline(
        scenarios=(BaselineScenario(name="tiny", dimension=4, pop_size=16, generations=4),),
        repeats=1,
        base_seed=7,
        output_dir=tmp_path,
    )

    assert Path(report["raw_csv"]).is_file()
    assert Path(report["summary_csv"]).is_file()
    assert Path(report["summary_json"]).is_file()
    assert report["summary"]
    row = report["summary"][0]
    assert row["scenario"] == "tiny"
    assert row["runs"] == 1
