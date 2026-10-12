from pathlib import Path
import pytest
from blackbase.project import build_case, load_case_builder, run_case
from nsgablack.catalog.registry import get_source_catalog, CatalogEntry
from nsgablack.catalog.usage import build_usage_profile
from nsgablack.catalog.recipes import ADAPTER_RECIPES, constructor_check
from nsgablack.catalog.sync import build_catalog_bundle


@pytest.mark.parametrize("key", ADAPTER_RECIPES)
def test_recipe_standard_case_runs_and_exports(key):
    root = Path(__file__).resolve().parents[1] / "examples/cases/catalog_recipes"
    solver = build_case(load_case_builder(root, key.split(".")[-1]), resource_context={"threads": 1})
    result = run_case(solver)
    assert result is not None
    assert solver.run_progress_steps > 0
    assert solver.evaluation_count > 0


def test_source_usage_has_no_invalid_constructor_recipes_or_fake_examples():
    errors = []
    for entry in get_source_catalog(profile="framework-core").list():
        if entry.kind not in {"adapter", "plugin", "representation", "bias"}:
            continue
        usage = build_usage_profile(entry)
        status, reasons = constructor_check(entry, usage.minimal_wiring)
        if status == "invalid":
            errors.append((entry.key, reasons))
        assert "catalog search" not in usage.example_entry
        assert usage.minimal_wiring[0].startswith("# recipe-status:")
    assert not errors


def test_static_health_does_not_claim_runtime_checks():
    entry = CatalogEntry(key="adapter.nsga2", title="NSGA2", kind="adapter", import_path="nsgablack.adapters:NSGA2Adapter")
    row = build_catalog_bundle(profile="framework-core", runtime=False, entries=[entry]).health[0]
    assert row.import_ok is None
    assert row.params_ok is None


def test_required_constructor_arguments_are_explicit_template_inputs():
    entry = CatalogEntry(key="bias.test_callable", title="Callable", kind="bias", import_path="nsgablack.bias:CallableBias")
    usage = build_usage_profile(entry)
    assert usage.wiring_status == "template"
    assert constructor_check(entry, usage.minimal_wiring)[0] == "signature-checked"
