import json
from pathlib import Path


def test_runtime_surface_tracker_materializes_solver_run_surface(sample_problem, sample_bias, tmp_path: Path):
    from nsgablack.adapters import SAConfig, SimulatedAnnealingAdapter
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.plugins import (
        ModuleReportConfig,
        ModuleReportPlugin,
        RuntimeSurfaceTrackerConfig,
        RuntimeSurfaceTrackerPlugin,
        list_runtime_artifact_surfaces,
        list_runtime_run_surfaces,
    )
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer

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

    db_path = tmp_path / "runtime_surface.sqlite3"
    solver.add_plugin(
        ModuleReportPlugin(
            config=ModuleReportConfig(
                output_dir=str(tmp_path),
                run_id="runtime_demo",
                write_bias_markdown=False,
            )
        )
    )
    solver.add_plugin(
        RuntimeSurfaceTrackerPlugin(
            config=RuntimeSurfaceTrackerConfig(
                db_path=str(db_path),
                namespace="ut_runtime",
                tag="smoke",
            )
        )
    )

    solver.max_steps = 3
    result = solver.run()

    assert db_path.exists()
    assert isinstance(result, dict)
    assert "run_surface" in result

    run_surface = dict(result["run_surface"])
    surface_record = dict(run_surface["surface_record"])
    assembly_record = dict(run_surface["assembly_record"])
    run_record = dict(run_surface["run_record"])
    artifact_records = [dict(row) for row in run_surface["artifact_records"]]

    assert surface_record["framework"] == "nsgablack"
    assert surface_record["surface_kind"] == "solver"
    assert str(surface_record["surface_key"]).startswith("solver:")
    assert str(run_record["run_id"]).strip()
    assert run_record["surface_kind"] == "solver"
    assert str(run_record["driver_ref"]).startswith("adapter:")
    assert str(assembly_record["assembly_signature"]).strip()
    assert "representation_slots" in dict(assembly_record.get("component_slots_json", {}))

    artifact_ids = {str(row.get("artifact_id")) for row in artifact_records}
    assert "modules_report_json" in artifact_ids
    assert "bias_report_json" in artifact_ids
    assert "runtime_surface_db" in artifact_ids

    run_rows = list_runtime_run_surfaces(db_path, status=str(result.get("status")), limit=10)
    assert len(run_rows) == 1
    run_row = run_rows[0]
    assert dict(run_row["surface_record_json"])["framework"] == "nsgablack"
    assert dict(run_row["assembly_record_json"])["assembly_signature"] == assembly_record["assembly_signature"]
    assert dict(run_row["run_record_json"])["run_id"] == run_record["run_id"]

    artifact_rows = list_runtime_artifact_surfaces(db_path, run_id=str(run_record["run_id"]), limit=20)
    stored_artifact_ids = {str(row.get("artifact_id")) for row in artifact_rows}
    assert "modules_report_json" in stored_artifact_ids
    assert "runtime_surface_db" in stored_artifact_ids

    modules_path = tmp_path / "runtime_demo.modules.json"
    assert modules_path.exists()
    modules_payload = json.loads(modules_path.read_text(encoding="utf-8"))
    assert modules_payload["metadata"]["run_id"] == "runtime_demo"
