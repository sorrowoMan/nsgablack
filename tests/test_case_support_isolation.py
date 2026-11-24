from pathlib import Path
from blackbase.project import build_case, load_case_builder, run_case
from nsgablack.project.case_support.pipeline_config import create_bindings


def test_case_factory_registrations_do_not_leak():
    first, second = create_bindings(), create_bindings()
    sentinel = object()
    first.register_pipeline_builder("default", lambda _: sentinel)
    assert first.build_pipeline(first.get_pipeline_registry(), "default") is sentinel
    assert second.build_pipeline(second.get_pipeline_registry(), "default") is not sentinel


def test_two_migrated_cases_build_independently_and_export():
    root = Path(__file__).resolve().parents[1]
    for case in ("multi_strategy", "single_trajectory"):
        solver = build_case(load_case_builder(root / "examples/cases" / case, case),
                            resource_context={"threads": 1, "workers": 1})
        solver.set_max_steps(1)
        assert run_case(solver) is not None
