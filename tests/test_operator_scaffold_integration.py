"""Exercise optional direct operators through a real generated Case and L0 grant."""

import importlib.util
from pathlib import Path

import numpy as np

from blackbase.project import build_case, load_case_builder, run_case
from blackbase.resources import ResourceAllocator, ResourceContext, ResourceRequest
from nsgablack.project import run_project_doctor
from nsgablack.project.scaffold import add_case, create_project
from nsgablack.representation.continuous import GaussianMutation
from nsgablack.utils.runtime_contracts import inspect_runtime_contracts


def test_generated_case_direct_mutator_build_run_and_checkpoint(tmp_path, monkeypatch):
    root = create_project(tmp_path / "operator_project")
    case = add_case("operator_search", "solver", project_root=root)
    example = case / "adapter" / "operator_example.py"
    template = (Path(__file__).resolve().parents[1] / "project" / "scaffold"
                / "case_template_solver" / "adapter" / "operator_example.py")
    assert example.read_bytes() == template.read_bytes()

    # Customize only the generated Case's assembly, as its author would. The
    # canonical builder and component_overrides contract remain intact, so the
    # Doctor build below exercises the optional direct binding as well.
    build_file = case / "build_solver.py"
    source = build_file.read_text(encoding="utf-8")
    source = source.replace(
        "from .pipeline import build_pipeline",
        "from .pipeline import build_pipeline\n"
        "from .adapter.operator_example import build_operator_adapter",
        1,
    ).replace(
        "    pipeline = build_pipeline(",
        '    component_overrides = {"adapter": build_operator_adapter(),\n'
        "                           **dict(component_overrides or {})}\n"
        "    pipeline = build_pipeline(",
        1,
    )
    build_file.write_text(source, encoding="utf-8")
    pipeline_file = case / "pipeline" / "main.py"
    pipeline_source = pipeline_file.read_text(encoding="utf-8")
    mutation_slot = '                    {"slot": "mutate", "operators": ("mutate",)},\n'
    assert mutation_slot in pipeline_source
    # Customize the Case's data pipeline in its normal configuration location.
    # The adapter's direct operator must work without a pipeline mutation slot.
    pipeline_file.write_text(pipeline_source.replace(mutation_slot, "", 1), encoding="utf-8")

    # This is the same execution-bearing switch as `project doctor --build`.
    report = run_project_doctor(root, instantiate_solver=True)
    errors = [(item.code, item.message) for item in report.diagnostics if item.level == "error"]
    assert not errors, errors
    assert any(item.code == "build-entry-instantiated" for item in report.diagnostics)

    spec = importlib.util.spec_from_file_location("generated_operator_example", example)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # parent_pool is deliberately omitted: this Case has no published archive.
    adapter = module.build_operator_adapter(mutation_sigma=0.2)
    mutator = adapter.get_bound_mutator()
    assert isinstance(mutator, GaussianMutation)
    calls = []
    mutate = mutator.mutate

    def observe_mutation(candidate, context=None):
        before = np.array(candidate, copy=True)
        result = mutate(candidate, context)
        calls.append((before, np.array(result, copy=True)))
        return result

    monkeypatch.setattr(mutator, "mutate", observe_mutation)
    allocator = ResourceAllocator()
    lease = allocator.acquire(ResourceRequest(threads=1, workers=1),
                              owner_id="operator_project", scope="optimization")
    resource = ResourceContext.from_mapping(
        lease.resource_context(namespace="operator_project.operator_search")
    )
    try:
        solver = build_case(
            load_case_builder(root, "operator_search"),
            resource_context=resource,
            component_overrides={"adapter": adapter},
        )
        assert solver.adapter is adapter
        assert solver.resource_context.lease["lease_id"] == lease.lease_id
        assert solver.resource_binding_audit["current"] is True
        assert solver.representation_pipeline.mutator is None
        assert inspect_runtime_contracts(solver) == ()

        result = run_case(solver)
        assert result is not None
        assert solver.run_progress_steps == 2
        assert solver.evaluation_count > 0
        assert calls, "The bound mutator must execute inside the real Case run"
        assert any(not np.array_equal(before, after) for before, after in calls)
        assert inspect_runtime_contracts(solver) == ()

        components = solver.checkpoint_components()
        assert components["adapter"] is adapter
        assert all(component is not mutator for component in components.values())
        bindings = adapter.get_local_operator_bindings()
        assert set(bindings) == {"mutator"}
        assert bindings["mutator"].component is mutator
        state = components["adapter"].get_state()["operator_bindings"]["mutator"]
        assert state["identity"] == mutator.checkpoint_identity()
        assert state["state"] == mutator.get_state()
    finally:
        allocator.release(lease)
