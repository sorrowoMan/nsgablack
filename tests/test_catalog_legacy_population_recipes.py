"""Legacy discoverability must not manufacture normal population-bias wiring."""

from __future__ import annotations

import ast
from pathlib import Path
import tomllib

import pytest

from nsgablack.catalog.recipes import ADAPTER_RECIPES
from nsgablack.catalog.registry import CatalogEntry, get_source_catalog
from nsgablack.catalog.usage import build_usage_profile
from nsgablack.catalog.examples import _base_record
from nsgablack.catalog.curation_seed import extract_source_guide_seed
from nsgablack.catalog.usage_learning import documentation_fields, select_documentation_guide, snippet_parts


LEGACY = {
    "bias.diversity": "DiversityBias",
    "bias.diversity_adaptive": "AdaptiveDiversityBias",
    "bias.diversity_crowding": "CrowdingDistanceBias",
    "bias.diversity_sharing": "SharingFunctionBias",
    "bias.diversity_niche": "NicheDiversityBias",
}
GUIDE = "docs/catalog_usage/POPULATION_PREFERENCE_APPLICATIONS_CN.md"


@pytest.fixture(scope="module")
def focused_manifest_specs():
    directory = Path(__file__).resolve().parents[1] / "catalog" / "example_manifests"
    return [(path.name, spec) for path in sorted(directory.glob("*.toml"))
            for spec in tomllib.loads(path.read_text(encoding="utf-8-sig")).get("example", ())
            if spec.get("binding", "focused") == "focused"]


def assert_migration_guidance(lines):
    assert lines  # An empty tuple would trigger generic constructor inference.
    assert all(line.startswith("#") for line in lines)
    assert ast.parse("\n".join(lines)).body == []
    text = "\n".join(lines)
    assert GUIDE in text
    assert "bias.unit_preference" in text and "bias.population_diversity" in text
    assert "不等价" in text
    assert "bias_module.add(" not in text


@pytest.mark.parametrize("key", LEGACY)
def test_legacy_recipe_overrides_are_nonempty_explanation_only(key):
    assert_migration_guidance(ADAPTER_RECIPES[key])


@pytest.mark.parametrize("key,symbol", LEGACY.items())
def test_empty_legacy_wiring_uses_guidance_instead_of_generic_add(key, symbol):
    entry = CatalogEntry(key=key, title=symbol, kind="bias",
        import_path="nsgablack.bias.algorithmic.diversity:" + symbol,
        config_keys=("weight",), example_entry=GUIDE)
    usage = build_usage_profile(entry)
    assert_migration_guidance(usage.minimal_wiring)
    assert usage.wiring_status == "guidance"
    assert usage.minimal_wiring[0].startswith("# recipe-status: guidance;")
    assert "signature-checked" not in "\n".join(usage.minimal_wiring)
    assert (Path(__file__).resolve().parents[1] / usage.example_entry).is_file()


@pytest.mark.parametrize("key", LEGACY)
def test_legacy_more_usage_contains_only_explicit_migration_binding(key, focused_manifest_specs):
    matches = [(filename, spec) for filename, spec in focused_manifest_specs if key in spec.get("component_keys", ())]
    original = [(filename, spec) for filename, spec in matches if filename == "population_preferences.toml"]
    assert len(original) == 1
    filename, spec = original[0]
    assert spec["id"] == "population-preference-migration-" + key
    assert not spec["id"].startswith("usage-")
    assert "旧类未装配" in spec["title"]
    assert spec["kind"] == "documentation" and not spec.get("run_command")
    assert spec["sources"] == [{"path": "nsgablack/" + GUIDE, "section": key}]
    # New complete migration material can coexist with the original per-key
    # source. It must be explicit, never another normal wiring or runnable Case.
    for extra_filename, extra in matches:
        if (extra_filename, extra) == original[0]:
            continue
        assert extra.get("usage_status") == "migration_reference"
        assert extra["kind"] == "documentation" and not extra.get("run_command")
        assert "未装配" in extra["title"]
    assert all(not source["path"].endswith("NSGABLACK_COMPONENT_USAGE_CN.md")
               for _, matched in matches for source in matched["sources"])
    root = Path(__file__).resolve().parents[1]
    roots = {name: root.parent / name for name in ("nsgablack", "blackbase", "mlblack")}
    records = [_base_record(matched, roots, None) for _, matched in matches]
    selected = select_documentation_guide(records)
    assert selected is not None and selected.get("usage_status") == "migration_reference"
    assert selected["kind"] == "documentation" and not selected["run_command"]
    assert selected["verification"]["status"] == "source_checked"
    assert {"什么时候用", "先准备什么", "放在哪", "接入步骤", "怎样判断接对", "运行入口"} <= documentation_fields(selected["snippets"]).keys()
    assert extract_source_guide_seed(records) is None
    for record in records:
        for snippet in record["snippets"]:
            for kind, code, language in snippet_parts(snippet):
                if kind == "code" and language == "python":
                    calls = [node for node in ast.walk(ast.parse(code)) if isinstance(node, ast.Call)]
                    assert not any((isinstance(node.func, ast.Name) and node.func.id in LEGACY.values())
                                   or (isinstance(node.func, ast.Attribute) and node.func.attr in LEGACY.values())
                                   for node in calls)
    # The shared historical book remains available for source review. It must
    # no longer be an active focused card for these migration-only components.
    old_book = root / "docs/catalog_usage/NSGABLACK_COMPONENT_USAGE_CN.md"
    assert old_book.is_file()


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_public_source_catalog_keeps_legacy_keys_as_non_executable_guidance(profile, monkeypatch):
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_MODE", "off")
    catalog = get_source_catalog(profile=profile)
    entries = {entry.key: entry for entry in catalog.list()}
    for key in LEGACY:
        entry = entries[key]
        assert_migration_guidance(entry.minimal_wiring)
        assert entry.minimal_wiring[0].startswith("# recipe-status: guidance;")
        assert build_usage_profile(entry).wiring_status == "guidance"
        assert entry.example_entry == GUIDE
        assert entry.required_companions != ("(none)",)
        assert {"bias.unit_preference", "bias.population_diversity"} <= set(entry.companions)
    # The supported path remains separately discoverable; a migration notice
    # must not remove either legacy symbols or the actual Unit components.
    assert "bias.unit_preference" in entries and "bias.population_diversity" in entries
