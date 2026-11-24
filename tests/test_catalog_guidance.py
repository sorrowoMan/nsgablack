from dataclasses import replace

import pytest

from nsgablack.catalog import facade
from nsgablack.catalog.contract_relations import enrich_entry_relation_fields
from nsgablack.catalog.guidance import guidance_for, guidance_payload
from nsgablack.catalog.registry import Catalog, CatalogEntry


def _entry(**kwargs):
    values = dict(
        key="tool.example_pool", title="Example pool", kind="tool",
        import_path="nsgablack.adapters:Pool", config_keys=("parent", "name"),
        minimal_wiring=("from nsgablack.adapters import Pool",),
        contract={"catalog": {
            "role": "pool", "concepts": ["精英保留", "候选区域"],
            "operations": ["chosen", "inject"],
            "boundaries": ["选择不会自动执行评估"],
        }},
    )
    values.update(kwargs)
    return CatalogEntry(**values)


@pytest.fixture
def source_catalog(monkeypatch):
    entry = _entry()
    catalog = Catalog([entry])
    context = facade.CatalogContext(
        catalog=catalog, scope="framework", profile="framework-core",
        project_root=None, include_global=False, project_found=True,
        effective_source="registry",
    )
    route = facade.CatalogReadRoute(
        profile="framework-core", source_mode="off", effective_source="registry", db_store=None,
    )
    monkeypatch.setattr(facade, "_load_catalog_context", lambda **kwargs: context)
    monkeypatch.setattr(facade, "_resolve_read_route", lambda **kwargs: route)
    return entry


def test_guidance_is_read_only_and_never_imports_or_constructs_a_unit(monkeypatch):
    def forbidden_load(self):
        pytest.fail("descriptive Catalog reads must not load or build a component")

    monkeypatch.setattr(CatalogEntry, "load", forbidden_load)
    entry = _entry()
    before = dict(entry.contract)
    assert guidance_for(entry).operations == ("chosen", "inject")
    assert entry.contract == before
    assert guidance_for(replace(entry, contract={})).role == "tool"


@pytest.mark.parametrize("declared", [None, [], {"role": 42}, {"concepts": "精英"},
                                      {"operations": [None]}, {"boundaries": [""]}])
def test_malformed_guidance_has_component_and_field_diagnostics(declared):
    with pytest.raises(TypeError, match=r"tool\.example_pool: contract\.catalog"):
        guidance_for(_entry(contract={"catalog": declared}))


@pytest.mark.parametrize("field", ["all", "usage"])
def test_concept_and_operation_search_do_not_require_knowing_component_kind(field):
    catalog = Catalog([_entry()])
    assert [entry.key for entry in catalog.search("精英保留", fields=field)] == ["tool.example_pool"]
    assert [entry.key for entry in catalog.search("inject", fields=field)] == ["tool.example_pool"]
    assert catalog.search("精英保留", fields="name") == []


def test_source_schema_facets_filters_and_payload_share_guidance(source_catalog):
    hits = facade.search_entries("精英保留", source_mode="off", field_filters={"role": "pool"})
    assert [entry.key for entry in hits] == [source_catalog.key]
    assert facade.list_entries(source_mode="off", field_filters={"role": "adapter"}) == []
    schema = facade.catalog_schema(source_mode="off")
    assert {"role", "concepts", "operations", "boundaries", "wiring_status"} <= set(schema["fields"])
    facets = facade.catalog_facets(source_mode="off")["facets"]
    assert {row["value"] for row in facets["concepts"]} == {"精英保留", "候选区域"}
    snapshot = facade.catalog_ui_snapshot(query="精英保留", selected_key=source_catalog.key, source_mode="off")
    selected = snapshot["selected"]
    assert selected["operations"] == ("chosen", "inject")
    assert selected["config_keys"] == ("parent", "name")
    assert selected["wiring_status"] == "guidance"
    assert selected["wiring_notes"]


def test_relation_enrichment_preserves_guidance_and_source_metadata():
    entry = _entry(context_requires=("artifact_ref",), metadata={"source": "private"})
    enriched = enrich_entry_relation_fields(entry)
    assert "artifact_ref" in enriched.artifact_requires
    assert enriched.contract == entry.contract
    assert enriched.metadata == entry.metadata
    assert guidance_payload(enriched) == guidance_payload(entry)


def test_detail_guidance_is_searchable_in_the_same_catalog(tmp_path):
    details = tmp_path / "details.toml"
    details.write_text('[detail.contract.catalog]\nrole="pool"\nconcepts=["局部搜索起点"]\n', encoding="utf-8")
    entry = _entry(contract={}, detail_ref=str(details))
    catalog = Catalog([entry])
    hits = catalog.search("局部搜索起点")
    assert [hit.key for hit in hits] == [entry.key]
    assert guidance_for(hits[0]).concepts == ("局部搜索起点",)
    assert guidance_for(catalog.list()[0]).concepts == ("局部搜索起点",)
    assert guidance_for(catalog.get(entry.key)).concepts == ("局部搜索起点",)


def test_catalog_upsert_preserves_guidance_when_only_description_changes(tmp_path):
    from blackbase.catalog import load_catalog_toml
    from nsgablack.catalog.quick_add import upsert_catalog_entry

    entry = _entry(metadata={"owner": "case-a"}, artifact_requires=("dataset",))
    target = tmp_path / "entries.toml"
    upsert_catalog_entry(target, entry.as_dict())
    upsert_catalog_entry(target, {
        "key": entry.key, "kind": entry.kind, "title": "Updated pool",
        "import_path": entry.import_path, "summary": "updated description",
    })
    restored, = load_catalog_toml(target)
    assert restored.title == "Updated pool"
    assert guidance_payload(restored) == guidance_payload(entry)
    assert restored.artifact_requires == entry.artifact_requires
    assert restored.metadata == entry.metadata
    upsert_catalog_entry(target, {
        "key": entry.key, "kind": entry.kind, "title": entry.title,
        "import_path": entry.import_path, "summary": "cleared guidance", "contract": {},
    })
    cleared, = load_catalog_toml(target)
    assert cleared.contract == {}


def test_related_alternatives_are_not_inferred_as_mandatory_components():
    from nsgablack.catalog.usage import build_usage_profile

    entry = _entry(companions=("adapter.bayesian_optimization", "adapter.cmaes"))
    assert build_usage_profile(entry).required_companions == ("(none)",)
    required = replace(entry, required_companions=("tool.unit_binding",))
    assert build_usage_profile(required).required_companions == ("tool.unit_binding",)


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_detail_facts_reach_bundle_and_digest_without_bypassing_profile(tmp_path, monkeypatch, profile):
    from nsgablack.catalog import registry
    from nsgablack.catalog.fingerprint import catalog_entries_digest
    from nsgablack.catalog.sync import build_catalog_bundle

    details = tmp_path / "details.toml"

    def write_detail(concept):
        details.write_text(
            f'[detail]\nexample_entry="examples/cases/demo/run_solver.py"\n'
            f'[detail.contract.catalog]\nrole="pool"\nconcepts=["{concept}"]\n', encoding="utf-8",
        )

    entry = _entry(contract={}, detail_ref=str(details))
    monkeypatch.setattr(registry, "_load_external_entries", lambda: [entry])
    monkeypatch.setattr(registry, "_load_entrypoint_entries", lambda: [])
    monkeypatch.setattr(registry, "_SOURCE_CATALOG_BY_PROFILE", {})
    write_detail("局部搜索起点")
    catalog = registry.get_source_catalog(refresh=True, profile=profile)
    resolved = catalog.list()
    assert guidance_for(resolved[0]).concepts == ("局部搜索起点",)
    bundle = build_catalog_bundle(profile=profile)
    assert bundle.components[0].contract == resolved[0].contract
    assert bundle.source_digest == catalog_entries_digest(resolved)
    expected_example = resolved[0].example_entry
    if profile == "framework-core":
        assert "examples/" not in expected_example
    else:
        assert expected_example == "examples/cases/demo/run_solver.py"
    assert catalog.get(entry.key).example_entry == expected_example
    assert catalog.search("局部搜索起点")[0].example_entry == expected_example
    before = bundle.source_digest
    write_detail("另一个起点规则")
    refreshed = registry.get_source_catalog(refresh=True, profile=profile)
    assert catalog_entries_digest(refreshed.list()) != before
