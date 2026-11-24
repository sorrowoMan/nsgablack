"""Public operation discovery and optional standard-Case assembly stay aligned."""
from __future__ import annotations

import importlib.util
from functools import partial
from pathlib import Path
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 is supported by the package.
    import tomli as tomllib

import pytest

from blackbase.project import build_case, load_case_builder, run_case
from blackbase.resources import ResourceAllocator, ResourceContext, ResourceRequest
from nsgablack.adapters import (
    ChangeBatchResult, ChangeRequest, ChangeResult, Pool, PoolEdit, PoolMaintenanceRequest, PoolOutput,
    DifferentialEvolutionAdapter, FeasibilityFirstSelection, MOEADAdapter,
    NSGA2Adapter, NSGA3Adapter, SimulatedAnnealingAdapter, SPEA2Adapter, VNSAdapter,
    partition,
)
from nsgablack.catalog import get_catalog
from nsgablack.project.scaffold import add_case, create_project
from nsgablack.representation import ContextGaussianMutation, UniformInitializer
from nsgablack.utils.extension_contracts import inspect_adapter_operator_bindings


REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "project" / "scaffold" / "case_template_solver" / "adapter" / "operator_example.py"


def load_example(path=TEMPLATE):
    spec = importlib.util.spec_from_file_location("optional_operation_example", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_operation_catalog_profiles_import_and_describe_the_real_surface(profile):
    catalog = get_catalog(profile=profile, refresh=True)
    expected = {
        "tool.selection_request", "tool.feasibility_first_selection", "tool.operator_binding",
        "tool.parent_selection_request", "tool.mixed_pool_parent_selector", "repr.gaussian_mutation",
        "repr.continuous", "repr.context_gaussian",
        "tool.change_request", "tool.change_result", "tool.change_batch_result", "tool.pool",
        "tool.pool_maintenance_request", "tool.pool_partition", "tool.pool_output", "tool.pool_edit", "tool.change_selection",
    }
    for key in expected:
        entry = catalog.get(key)
        assert entry is not None, key
        assert entry.load() is not None
        assert "examples/" not in entry.example_entry.replace("\\", "/")
    for key in ("adapter.nsga2", "adapter.nsga3", "adapter.spea2", "adapter.de", "adapter.moead",
                "adapter.sa", "adapter.vns", "adapter.pattern_search", "adapter.single_trajectory_adaptive"):
        entry = catalog.get(key)
        assert set(entry.load().operation_methods).issubset(set(entry.config_keys)), key
    assert "proposal_order" in catalog.get("adapter.sa").summary
    assert "replacement" in catalog.get("adapter.de").summary
    assert "survivor" in catalog.get("adapter.nsga2").summary
    assert "pool" in catalog.get("tool.change_request").config_keys
    assert set(catalog.get("tool.change_result").config_keys) == {"candidate", "source_refs", "outputs", "edits"}
    assert set(catalog.get("tool.pool_output").config_keys) == {"name", "create"}
    assert catalog.get("tool.change_request").load() is ChangeRequest
    assert catalog.get("tool.change_result").load() is ChangeResult
    assert catalog.get("tool.pool_output").load() is PoolOutput
    assert catalog.get("tool.pool_edit").load() is PoolEdit
    assert catalog.get("tool.change_batch_result").load() is ChangeBatchResult
    assert catalog.get("tool.pool").load() is Pool
    assert catalog.get("tool.pool_maintenance_request").load() is PoolMaintenanceRequest
    assert catalog.get("tool.pool_partition").load() is partition
    assert set(catalog.get("tool.pool_partition").config_keys) == {"pool", "by", "rng"}
    assert "具名副Pool" in catalog.get("tool.pool").summary
    assert any("return members" in line for line in catalog.get("tool.pool").minimal_wiring)
    assert set(catalog.get("tool.change_batch_result").config_keys) == {"results"}
    assert "max_outputs" in catalog.get("tool.change_request").config_keys
    if profile == "framework-core":
        assert all(entry.kind not in {"doc", "example"} for entry in catalog.list())


def test_new_operation_entries_have_one_source_authority():
    keys = ("tool.selection_request", "tool.feasibility_first_selection", "repr.continuous", "repr.context_gaussian",
            "tool.change_request", "tool.change_result", "tool.change_batch_result", "tool.pool",
            "tool.pool_maintenance_request", "tool.pool_partition", "tool.pool_output", "tool.pool_edit", "tool.change_selection")
    occurrences = {key: [] for key in keys}
    for path in (REPO / "catalog" / "entries").glob("*.toml"):
        for entry in tomllib.loads(path.read_text(encoding="utf-8-sig")).get("entry", ()):
            if entry["key"] in occurrences:
                occurrences[entry["key"]].append(path.name)
    assert all(len(paths) == 1 for paths in occurrences.values()), occurrences


def inspected_pool_change(request, *, rng):
    """An ordinary declared workflow; inspection must not access its live pool."""
    selected = request.pool.subpool("elite").random(1, rng=rng)
    return ChangeResult((request.candidate + selected.values[0]) / 2,
                        source_refs=selected.refs,
                        outputs=(PoolOutput("offspring", create=True),))


@pytest.mark.parametrize("algorithm", ["nsga2", "nsga3", "spea2", "vns", "moead"])
def test_pool_change_factory_is_inspectable_without_creating_unit_or_running_function(algorithm):
    adapter = load_example().build_operator_adapter(algorithm=algorithm, change=inspected_pool_change)
    unit_fields = ("current_unit", "neighborhood_unit") if algorithm == "vns" else ("algorithm_unit",)
    assert all(getattr(adapter, name) is None for name in unit_fields)
    assert inspect_adapter_operator_bindings(adapter) == ()
    assert all(getattr(adapter, name) is None for name in unit_fields)
    assert set(adapter.get_local_operator_bindings()) == {"change"}
    identity = adapter.get_bound_change().checkpoint_identity()
    assert identity["schema"] == "nsgablack.plain_change/v1"
    assert "ChangeResult" in identity["function"]["dependencies"]
    assert "PoolOutput" in identity["function"]["dependencies"]


def inspected_maintenance(request, *, rng):
    raise AssertionError("inspection executed maintenance")


def inspected_choose(pool):
    raise AssertionError("inspection executed ordinary Pool choice")


@pytest.mark.parametrize("algorithm", ["nsga2", "nsga3", "spea2", "vns", "moead"])
def test_optional_maintenance_factory_is_lazy_and_owned_once(algorithm):
    adapter = load_example().build_operator_adapter(algorithm=algorithm,
        change=inspected_pool_change, pool_maintenance=inspected_maintenance)
    assert inspect_adapter_operator_bindings(adapter) == ()
    assert set(adapter.get_local_operator_bindings()) == {"change", "pool_maintenance"}
    assert adapter.get_operator_unit() is None
    contract = adapter.get_operation_contract()["selection"]["pool_maintenance"]
    assert contract["method"] == "maintain" and contract["binding"] is not None


def test_factory_binds_ordinary_choose_without_executing_or_creating_unit():
    adapter = load_example().build_operator_adapter(selector=inspected_choose)
    assert inspect_adapter_operator_bindings(adapter) == ()
    assert adapter.get_operator_unit() is None
    assert adapter.get_bound_selector().checkpoint_identity()["schema"] == "nsgablack.pool_selection/v1"


def test_factory_partition_example_is_an_optional_lazy_ordinary_choice():
    example = load_example()
    adapter = example.build_operator_adapter(selector=partial(
        example.choose_with_partition, count=8, elite_count=2))
    assert inspect_adapter_operator_bindings(adapter) == ()
    assert adapter.get_operator_unit() is None
    assert adapter.get_bound_selector().checkpoint_identity()["schema"] == "nsgablack.pool_selection/v1"


def test_factory_named_outputs_example_is_lazy_and_preserves_plain_choice():
    example = load_example()
    adapter = example.build_operator_adapter(selector=partial(
        example.choose_with_outputs, count=8, elite_count=2))
    assert inspect_adapter_operator_bindings(adapter) == ()
    assert adapter.get_operator_unit() is None
    identity = adapter.get_bound_selector().checkpoint_identity()
    assert identity["schema"] == "nsgablack.pool_selection/v1"
    assert "partition" in identity["function"]["partial"]["dependencies"]
    assert callable(example.choose_with_partition)


@pytest.mark.parametrize("name,kind", [
    ("nsga2", NSGA2Adapter), ("nsga3", NSGA3Adapter), ("spea2", SPEA2Adapter),
    ("de", DifferentialEvolutionAdapter), ("moead", MOEADAdapter),
    ("sa", SimulatedAnnealingAdapter), ("vns", VNSAdapter),
])
def test_optional_factory_preserves_native_selection_until_explicitly_overridden(name, kind):
    build = load_example().build_operator_adapter
    adapter = build(algorithm=name)
    assert isinstance(adapter, kind)
    assert set(adapter.get_local_operator_bindings()) == {"mutator"}
    assert adapter.get_bound_selector() is None
    assert adapter.get_bound_initializer() is None
    if name in {"sa", "vns"}:
        assert isinstance(adapter.get_bound_mutator(), ContextGaussianMutation)
    initializer, selector = UniformInitializer(low=-1, high=1), FeasibilityFirstSelection()
    explicit = build(algorithm=name, initializer=initializer, selector=selector)
    assert explicit.get_bound_initializer() is initializer
    assert explicit.get_bound_selector() is selector
    assert explicit.get_bound_mutator() is not adapter.get_bound_mutator()


def test_optional_factory_rejects_parent_pool_on_non_parent_roles_and_unscoped_repair():
    build = load_example().build_operator_adapter
    with pytest.raises(ValueError, match="parent_pool"):
        build(algorithm="vns", parent_pool="elite")
    with pytest.raises(ValueError, match="JointRepairPolicy"):
        build(adapter_params={"repair": object()})
    with pytest.raises(ValueError, match="pool maintenance"):
        build(algorithm="de", pool_maintenance=inspected_maintenance)


@pytest.mark.parametrize("algorithm", ["de", "vns"])
def test_generated_case_uses_the_same_factory_and_formal_component_overrides(tmp_path, algorithm):
    root = create_project(tmp_path / f"operation_{algorithm}")
    case = add_case("search", "solver", project_root=root)
    example = case / "adapter" / "operator_example.py"
    assert example.read_bytes() == TEMPLATE.read_bytes()
    adapter = load_example(example).build_operator_adapter(
        algorithm=algorithm, population_size=4, offspring_size=2,
        initializer=UniformInitializer(low=0.25, high=0.25))
    allocator = ResourceAllocator()
    lease = allocator.acquire(ResourceRequest(threads=1, workers=1),
                              owner_id=f"operation_{algorithm}", scope="optimization")
    resource = ResourceContext.from_mapping(lease.resource_context(namespace=f"operation_{algorithm}.search"))
    try:
        solver = build_case(load_case_builder(root, "search"), resource_context=resource,
                            component_overrides={"adapter": adapter})
        assert solver.adapter is adapter
        assert solver.resource_binding_audit["current"] is True
        assert adapter.get_bound_selector() is None
        assert run_case(solver) is not None
        assert solver.run_progress_steps == 2
        assert set(adapter.get_local_operator_bindings()) == {"initializer", "mutator"}
        assert "operator_bindings" in adapter.get_state()
    finally:
        allocator.release(lease)
