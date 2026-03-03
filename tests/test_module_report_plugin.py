import json
from pathlib import Path


def test_module_report_writes_reports_and_injects_artifacts(sample_problem, sample_bias, tmp_path: Path):
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-10.0, high=10.0),
        mutator=ContextGaussianMutation(base_sigma=0.5, sigma_key="mutation_sigma"),
        repair=ClipRepair(low=-10.0, high=10.0),
    )

    solver = ComposableSolver(
        problem=sample_problem,
        adapter=SimulatedAnnealingAdapter(SAConfig(batch_size=6)),
        representation_pipeline=pipeline,
        bias_module=sample_bias,
    )

    attach_module_report(solver, output_dir=str(tmp_path), run_id="demo", write_bias_markdown=True)
    attach_benchmark_harness(solver, output_dir=str(tmp_path), run_id="demo", seed=123, log_every=1, flush_every=1, overwrite=True)

    solver.max_steps = 3
    solver.run()

    modules_path = tmp_path / "demo.modules.json"
    bias_json_path = tmp_path / "demo.bias.json"
    bias_md_path = tmp_path / "demo.bias.md"
    summary_path = tmp_path / "demo.summary.json"

    assert modules_path.exists()
    assert bias_json_path.exists()
    assert bias_md_path.exists()
    assert summary_path.exists()

    modules = json.loads(modules_path.read_text(encoding="utf-8"))
    assert modules["metadata"]["run_id"] == "demo"
    assert "plugins" in modules

    bias_report = json.loads(bias_json_path.read_text(encoding="utf-8"))
    assert bias_report["metadata"]["run_id"] == "demo"
    assert bias_report["enabled"] is True

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert "artifacts" in summary
    assert "bias_report_json" in summary["artifacts"]

