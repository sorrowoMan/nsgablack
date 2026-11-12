"""Current architecture is discoverable without changing stable kind/import keys."""
from pathlib import Path
import inspect
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import pytest

from nsgablack.catalog import guidance_for
from nsgablack.catalog.registry import CatalogEntry, get_source_catalog
from nsgablack.catalog.recipes import constructor_check


ROOT = Path(__file__).resolve().parents[1]


def source_records():
    values = {}
    for path in (ROOT / "catalog/entries").glob("*.toml"):
        for record in tomllib.loads(path.read_text(encoding="utf-8-sig")).get("entry", ()):
            assert record["key"] not in values, record["key"]
            values[record["key"]] = record
    return values


PARTS = {
    "adapter.bayesian_optimization": (
        "tool.bo_unit", "tool.bo_model", "tool.bo_acquisition", "tool.bo_acquisition_optimizer"),
    "adapter.cmaes": ("tool.cma_unit", "tool.cma_sampler", "tool.cma_ranking", "tool.cma_update"),
    "adapter.map_elites": (
        "tool.map_elites_unit", "tool.map_descriptor", "tool.map_cells", "tool.map_competition",
        "tool.map_sequence_emitter", "tool.map_gaussian_emitter"),
}


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_both_profiles_preserve_current_roles_and_reciprocal_assembly_links(profile):
    catalog = get_source_catalog(profile=profile, refresh=True)
    for owner, parts in PARTS.items():
        adapter = catalog.get(owner)
        assert adapter is not None and adapter.load() is not None
        assert guidance_for(adapter).role == "adapter"
        for key in parts:
            entry = catalog.get(key)
            assert entry is not None and entry.load() is not None, key
            assert key in adapter.companions and owner in entry.companions, key
            assert guidance_for(entry).concepts and guidance_for(entry).boundaries
    assert catalog.get("tool.unit_binding").load().__name__ == "UnitBinding"
    assert catalog.get("tool.population_unit").load().__name__ == "PopulationUnit"
    if profile == "framework-core":
        assert all(entry.kind not in {"example", "doc"} for entry in catalog.list())
        assert all("examples/" not in entry.import_path.replace("\\", "/") for entry in catalog.list())
        assert catalog.get("doc.architecture.catalog_usage") is None
    else:
        doc = catalog.get("doc.architecture.catalog_usage")
        assert doc.load() == "docs/architecture/CATALOG_USAGE_CN.md"
        assert (ROOT / doc.example_entry).is_file()


def test_unit_builders_keep_compatible_imports_and_explicit_non_pipeline_roles():
    records = source_records()
    catalog = get_source_catalog(profile="framework-core", refresh=True)
    binding = catalog.get("tool.unit_binding")
    builders = [record for key, record in records.items() if key.startswith("repr.unit_")]
    assert len(builders) >= 14
    for record in builders:
        entry = catalog.get(record["key"])
        assert entry.kind == "representation"
        assert entry.import_path.startswith("nsgablack.representation:")
        assert guidance_for(entry).role == "unit_builder"
        assert not {"pipeline", "algorithm-pipeline"}.intersection(entry.tags)
        assert record["config_keys"] == []
        assert "tool.unit_binding" in entry.companions
        assert entry.key in binding.companions
        builder = entry.load()
        assert all(callable(getattr(builder, name, None)) for name in ("build", "dump", "restore"))


@pytest.mark.parametrize("key", [
    "tool.solution_pool", "tool.pool", "tool.change_selection", "tool.subpools",
    "tool.unit_binding", "tool.population_unit", "tool.feature_unit",
    "tool.case_inner_runtime_evaluator",
    *[part for parts in PARTS.values() for part in parts],
])
def test_constructor_keys_and_operations_describe_actual_distinct_surfaces(key):
    record = source_records()[key]
    entry = CatalogEntry(**record)
    component = entry.load()
    if record["config_keys"]:
        parameters = inspect.signature(component).parameters
        assert set(record["config_keys"]) <= set(parameters), key
    for operation in guidance_for(entry).operations:
        assert hasattr(component, operation), (key, operation)
    # Config lists cannot silently become a grab bag of runtime methods.
    if key in {"tool.solution_pool", "tool.pool", "tool.change_selection"}:
        assert not set(record["config_keys"]).intersection(guidance_for(entry).operations)


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_complete_case_batch_has_usage_and_real_operations_in_both_profiles(profile):
    entry = get_source_catalog(profile=profile, refresh=True).get("tool.case_inner_runtime_evaluator")
    assert entry is not None and entry.load().__name__ == "CaseInnerRuntimeEvaluator"
    assert guidance_for(entry).operations == ("evaluate", "evaluate_batch")
    assert "max_workers" in entry.config_keys
    assert (ROOT / entry.example_entry).is_file()


def test_concepts_expose_real_bo_and_label_the_older_soft_preferences():
    records = source_records()
    real = CatalogEntry(**records["adapter.bayesian_optimization"])
    legacy = CatalogEntry(**records["bias.bayesian_guidance"])
    assert "贝叶斯引导" in guidance_for(real).concepts
    assert "贝叶斯引导" in guidance_for(legacy).concepts
    assert guidance_for(real).role == "adapter"
    assert guidance_for(legacy).role == "soft_preference"
    assert "占位" in " ".join(guidance_for(legacy).boundaries)
    assert "异步" in " ".join(guidance_for(real).boundaries)
    acquisition = CatalogEntry(**records["tool.bo_acquisition"])
    assert "替换采集函数" in guidance_for(acquisition).concepts


def test_new_component_recipes_bind_signatures_and_link_to_real_standard_cases():
    records = source_records()
    for parts in PARTS.values():
        for key in parts:
            entry = CatalogEntry(**records[key])
            case = ROOT / entry.example_entry
            assert case.name == "run_solver.py" and case.is_file(), key
            assert (case.parent / "build_solver.py").is_file()
            assert (case.parent / ".case").is_file()
            status, _ = constructor_check(entry, entry.minimal_wiring)
            assert status in {"signature-checked", "guidance"}, (key, status)


def test_declared_guidance_lists_are_well_formed_and_not_runtime_certificates():
    for record in source_records().values():
        if "catalog" not in record.get("contract", {}):
            continue
        entry = CatalogEntry(**record)
        guidance = guidance_for(entry)
        assert isinstance(guidance.role, str) and guidance.role
        assert all(isinstance(value, str) and value for values in (
            guidance.concepts, guidance.operations, guidance.boundaries) for value in values)
        assert "verified" not in record["contract"]["catalog"]
        assert "tests_passed" not in record["contract"]["catalog"]


def test_generated_indexes_keep_default_documents_separate_from_core_component_guidance(tmp_path, monkeypatch):
    # docs/development outputs are intentionally ignored; validate export in a
    # fresh directory so a clean checkout does not depend on local artifacts.
    from nsgablack.catalog.export import export_catalog_docs
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "off")
    outputs = {}
    for profile in ("default", "framework-core"):
        path = tmp_path / (profile + ".md")
        export_catalog_docs(profile=profile, output_path=path)
        outputs[profile] = path.read_text(encoding="utf-8")
    full, core = outputs["default"], outputs["framework-core"]
    assert "## `doc.architecture.catalog_usage`" in full
    assert "## `doc.architecture.catalog_usage`" not in core
    for content in (full, core):
        assert "## `tool.unit_binding`" in content
        assert "## `tool.bo_acquisition`" in content
        assert "Role: unit_builder" in content
        assert "Runtime operations:" in content
        assert "Wiring status:" in content
        assert "仅通过语法和构造签名检查；不等于行为已验证" in content
