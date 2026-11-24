"""New usage material stays complete, source bound and separate from execution."""
from __future__ import annotations

import ast
from pathlib import Path
try:
    import tomllib
except ImportError:
    import tomli as tomllib

import pytest

from nsgablack.catalog.examples import _base_record
from nsgablack.catalog.curation_seed import extract_source_guide_seed
from nsgablack.catalog.usage_api_validation import inspect_usage_api
from nsgablack.catalog.usage_learning import documentation_fields, snippet_parts


ROOT = Path(__file__).resolve().parents[1]
ROOTS = {name: ROOT.parent / name for name in ("nsgablack", "blackbase", "mlblack")}
MANIFESTS = ("finite_difference_application.toml", "candidate_operator_applications.toml",
             "observability_applications.toml", "population_preferences.toml", "pool_callback_application.toml",
             "adaptive_trajectory_application.toml", "algorithm_component_applications.toml",
             "ml_forecasting_applications.toml", "ml_structured_input_applications.toml",
             "ml_backend_contract_applications.toml", "domain_soft_score_applications.toml",
             "pool_selection_applications.toml", "candidate_layout_applications.toml",
             "ml_tabular_applications.toml", "external_observability_applications.toml",
             "ml_data_pipeline_applications.toml", "ml_model_composition_applications.toml",
             "structured_local_search_applications.toml")
MANIFESTS += tuple(sorted({path.name for pattern in (
    "bias_*.toml", "ml_bias_*.toml", "ml_neural_*.toml", "ml_symbolic_*.toml",
    "ml_conditional_*.toml", "ml_orthogonal_*.toml", "ml_core_*.toml", "ml_classical_*.toml",
    "ml_observation_*.toml", "ml_external_source_*.toml", "ml_framework_bridge_*.toml",
    "core_*.toml", "orchestration_*.toml", "lifecycle_*.toml",
) for path in (ROOT / "catalog" / "example_manifests").glob(pattern)} - set(MANIFESTS)))
SPECS = [item for name in MANIFESTS for item in tomllib.loads(
    (ROOT / "catalog" / "example_manifests" / name).read_text(encoding="utf-8"))["example"]]


@pytest.mark.parametrize("spec", SPECS, ids=lambda item: item["id"])
def test_application_source_has_complete_teaching_or_explicit_migration_scope(spec):
    record = _base_record(spec, ROOTS, None)
    assert record["kind"] == "documentation" and not record["run_command"]
    assert all(snippet["complete"] for snippet in record["snippets"])
    fields = documentation_fields(record["snippets"])
    if spec.get("usage_status") == "migration_reference":
        assert {"什么时候用", "先准备什么", "放在哪", "接入步骤", "怎样判断接对", "运行入口"} <= fields.keys()
        assert extract_source_guide_seed((record,)) is None
    elif spec["id"].startswith("population-preference-migration-"):
        assert "旧类未装配" in spec["title"]
        assert {"先准备什么", "放在哪"} <= fields.keys()
        assert extract_source_guide_seed((record,)) is None
    else:
        assert {"什么时候用", "先准备什么", "放在哪", "接入步骤", "怎样判断接对", "运行入口"} <= fields.keys()
        assert extract_source_guide_seed((record,)) is not None
    # A source-bound recipe is not an executed Project or a model approval.
    assert record["verification"]["status"] == "source_checked"
    assert "tutorial_review" not in record


@pytest.mark.parametrize("spec", SPECS, ids=lambda item: item["id"])
def test_application_python_and_proven_framework_calls_are_valid_without_execution(spec):
    record = _base_record(spec, ROOTS, None)
    code = [text for snippet in record["snippets"] for kind, text, language in snippet_parts(snippet)
            if kind == "code" and language == "python"]
    for block in code:
        ast.parse(block)
    if code:
        result = inspect_usage_api("\n\n".join(code), source_roots=ROOTS)
        assert result["issues"] == []
        # Unknown calls remain unknown; this test never executes the tutorial.
        assert isinstance(result["unknown_calls"], list)


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_corrected_catalog_parameters_and_legacy_boundaries_are_public(profile, monkeypatch):
    from nsgablack.catalog.registry import get_source_catalog

    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "off")
    catalog = get_source_catalog(profile=profile)
    entries = {entry.key: entry for entry in catalog.list()}
    benchmark = entries["plugin.benchmark_harness"]
    assert set(benchmark.config_keys) == {"output_dir", "run_id", "seed", "overwrite", "log_every", "flush_every"}
    # Public cards must name the fields accepted by the actual Config classes.
    mo = entries["adapter.trust_region_mo_dfo"]
    assert {"weight_method", "fixed_weights"} <= set(mo.config_keys)
    assert not {"scalarization", "weights"} & set(mo.config_keys)
    assert "plugin.pareto_archive" not in mo.required_companions
    nonsmooth = entries["adapter.trust_region_nonsmooth"]
    assert "score_mode" in nonsmooth.config_keys and "aggregation" not in nonsmooth.config_keys
    assert "print_latest_summary" in entries["plugin.mysql_run_logger"].config_keys
    for key in ("bias.diversity", "bias.diversity_adaptive", "bias.diversity_crowding",
                "bias.diversity_sharing", "bias.diversity_niche"):
        entry = entries[key]
        assert ast.parse("\n".join(entry.minimal_wiring)).body == []
        assert any("recipe-status: guidance" in line for line in entry.minimal_wiring)
        assert entry.required_companions != ("(none)",)
        assert "bias.unit_preference" in entry.companions
        assert entry.example_entry.endswith("POPULATION_PREFERENCE_APPLICATIONS_CN.md")
    if profile == "framework-core":
        assert all(entry.kind not in {"doc", "example"} for entry in catalog.list())


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_domain_bias_cards_expose_real_configuration_and_score_boundaries(profile, monkeypatch):
    from nsgablack.catalog.registry import get_source_catalog

    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "off")
    entries = {entry.key: entry for entry in get_source_catalog(profile=profile).list()}
    wiring = []
    for key in ("bias.preference", "bias.rule_based", "bias.constraint", "bias.structure_prior"):
        entry = entries[key]
        assert "weight" in entry.config_keys and "(none)" not in entry.config_keys
        assert "bias.module" in entry.required_companions
        assert entry.example_entry.endswith("DOMAIN_SOFT_SCORE_APPLICATIONS_CN.md")
        assert entry.contract["catalog"]["role"] == "soft_preference"
        assert entry.contract["catalog"]["boundaries"]
        wiring.extend(entry.minimal_wiring)
    # The cards must actually configure a cost, rather than attach empty defaults.
    source = "\n".join(wiring)
    assert ".add_constraint(" in source and ".add_rule(" in source
    assert "preference_functions=" in source and "pairs=" in source
    assert inspect_usage_api(source, source_roots=ROOTS)["issues"] == []
