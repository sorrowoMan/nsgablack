import json
from pathlib import Path


def test_benchmark_harness_writes_csv_and_summary(sample_problem, tmp_path: Path):
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.utils.suites import attach_benchmark_harness

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-10.0, high=10.0),
        mutator=ContextGaussianMutation(base_sigma=0.5, sigma_key="mutation_sigma"),
        repair=ClipRepair(low=-10.0, high=10.0),
    )

    solver = ComposableSolver(
        problem=sample_problem,
        adapter=SimulatedAnnealingAdapter(SAConfig(batch_size=6)),
        representation_pipeline=pipeline,
    )

    attach_benchmark_harness(
        solver,
        output_dir=str(tmp_path),
        run_id="demo",
        seed=123,
        log_every=1,
        flush_every=1,
        overwrite=True,
    )

    solver.max_steps = 5
    solver.run()

    csv_path = tmp_path / "demo.csv"
    summary_path = tmp_path / "demo.summary.json"
    assert csv_path.exists()
    assert summary_path.exists()

    text = csv_path.read_text(encoding="utf-8")
    assert "elapsed_s" in text
    assert "best_score" in text

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["run_id"] == "demo"
    assert summary["eval_count"] >= 0

