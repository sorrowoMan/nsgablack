"""Usage relationships are static evidence, never an algorithm execution."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from nsgablack.catalog import facade
from nsgablack.catalog.assembly_relations import build_assembly_neighbor_sections
from nsgablack.catalog.contracts import CatalogBundle, UsageContract
from nsgablack.catalog.registry import Catalog, CatalogEntry, get_source_catalog
from nsgablack.catalog.store.mysql import MySQLCatalogStore
from nsgablack.catalog.store.postgres import PostgresCatalogStore
from nsgablack.catalog.sync import _build_component, _build_context_contract
from tests.test_catalog_guidance_storage import LocalConnection, materialize_legacy


def component(key, path, *lines, **fields):
    return CatalogEntry(key=key, title=key, kind="tool", import_path=path,
                        minimal_wiring=lines, **fields)


def groups(payload):
    return payload["relation_groups"]


def test_explicit_import_aliases_and_module_aliases_retain_call_coordinates(monkeypatch):
    owner = component("owner", "demo:Owner", "from left import Widget as Build",
                      "import right as tools", "", "value = Build(\n    tools.Widget()\n)")
    left = component("left", "left:Widget")
    right = component("right", "right:Widget")
    monkeypatch.setattr(CatalogEntry, "load", lambda self: pytest.fail("Loaded a Catalog component"))
    payload = build_assembly_neighbor_sections(owner, candidates=[left, right])
    rows = groups(payload)["assembly_uses"]
    assert [row["key"] for row in rows] == ["left", "right"]
    evidence = rows[0]["evidence"][0]
    assert evidence["line"] == 4 and evidence["column"] == 9
    assert evidence["end_line"] == 6 and evidence["end_column"] == 2
    assert evidence["import_line"] == 1 and evidence["call"] == "Build"
    assert evidence["source_field"] == "minimal_wiring"
    assert evidence["import_path"] == "left:Widget"
    assert rows[1]["evidence"][0]["line"] == 5
    reverse = build_assembly_neighbor_sections(right, candidates=[owner, left])
    assert groups(reverse)["assembly_used_by"][0]["evidence"] == rows[1]["evidence"]


def test_imports_alone_comments_and_same_names_do_not_imply_relationships():
    owner = component("owner", "demo:Owner", "from left import Widget", "# Widget()", "text = 'Widget()'")
    left = component("left", "left:Widget")
    assert not groups(build_assembly_neighbor_sections(owner, candidates=[left]))
    raw = replace(owner, minimal_wiring=("Widget()",))
    payload = build_assembly_neighbor_sections(raw, candidates=[left, component("right", "right:Widget")])
    assert not groups(payload)
    assert payload["assembly_diagnostics"][0]["code"] == "missing-import"


def test_same_import_path_multiple_keys_is_ambiguous_and_self_is_exact():
    owner = component("owner", "left:Widget", "from left import Widget", "Widget()")
    assert not groups(build_assembly_neighbor_sections(owner))
    alternate = component("other-key", "left:Widget")
    payload = build_assembly_neighbor_sections(owner, candidates=[alternate])
    assert not groups(payload)
    assert payload["assembly_diagnostics"][0]["candidate_keys"] == ("other-key", "owner")
    other = component("owner.child", "right:Widget", "from left import Widget", "Widget()")
    rows = groups(build_assembly_neighbor_sections(owner, candidates=[other]))["assembly_used_by"]
    assert [row["key"] for row in rows] == ["owner.child"]


@pytest.mark.parametrize("source", [
    ("from left import Widget", "Widget = other", "Widget()"),
    ("from left import Widget", "def make(Widget):", "    Widget()"),
    ("def make():", "    from left import Widget", "Widget()"),
    ("from left import Widget", "def make():", "    Widget()", "    Widget = other"),
    ("if condition:", "    from left import Widget", "else:", "    from right import Widget", "Widget()"),
    ("from left import Widget", "[Widget() for Widget in choices]"),
    ("from left import Widget", "factory = lambda *Widget: Widget()"),
    ("try:", "    from left import Widget", "except ImportError:", "    from right import Widget", "Widget()"),
    ("for item in items:", "    from left import Widget", "Widget()"),
    ("class Group:", "    from left import Widget", "    def make(self):", "        return Widget()"),
])
def test_shadowed_and_ambiguous_scoped_bindings_do_not_guess(source):
    owner = component("owner", "demo:Owner", *source)
    payload = build_assembly_neighbor_sections(owner, candidates=[component("left", "left:Widget"),
                                                                component("right", "right:Widget")])
    assert not groups(payload)
    assert payload["assembly_status"] == "partial"


def test_missing_invalid_and_raw_declarations_are_explicit():
    missing = component("empty", "demo:Empty")
    assert build_assembly_neighbor_sections(missing)["assembly_status"] == "missing"
    invalid = replace(missing, minimal_wiring=("def incomplete(",))
    payload = build_assembly_neighbor_sections(invalid)
    assert payload["assembly_status"] == "invalid"
    assert payload["assembly_diagnostics"][0]["line"] == 1
    malformed = SimpleNamespace(key="bad", title="bad", kind="tool", summary="", import_path="demo:Bad",
                                minimal_wiring="Widget()")
    assert build_assembly_neighbor_sections(malformed)["assembly_diagnostics"][0]["code"] == "invalid-wiring"
    raw = component("raw", "demo:Raw", "from left import Widget", "def make():", "", "    return Widget()")
    original = raw.minimal_wiring
    payload = build_assembly_neighbor_sections(raw, candidates=[component("left", "left:Widget")])
    evidence = groups(payload)["assembly_uses"][0]["evidence"][0]
    assert evidence["line"] == 4 and evidence["column"] == 12
    assert evidence["source_line"] == "    return Widget()"
    assert raw.minimal_wiring == original
    bad_path = replace(missing, import_path="nsgablack.bad/path:Unsafe")
    assert any(item["code"] == "invalid-import-path" for item in
               build_assembly_neighbor_sections(bad_path)["assembly_diagnostics"])


def test_static_reexports_resolve_public_and_internal_paths_without_imports(monkeypatch):
    owner = component("owner", "demo:Owner", "from nsgablack.representation import ContextGaussianMutation as Move",
                      "Move(base_sigma=0.1)")
    target = component("repr.context_gaussian", "nsgablack.representation.continuous:ContextGaussianMutation")
    monkeypatch.setattr(CatalogEntry, "load", lambda self: pytest.fail("Loaded a Catalog component"))
    evidence = groups(build_assembly_neighbor_sections(owner, candidates=[target]))["assembly_uses"][0]["evidence"][0]
    assert evidence["resolution"] == "static-reexport"
    assert evidence["reexports"][0]["line"] > 0
    assert evidence["reexports"][0]["path"].replace("\\", "/").endswith("representation/__init__.py")
    internal = replace(owner, minimal_wiring=("from nsgablack.representation.continuous import ContextGaussianMutation",
                                             "ContextGaussianMutation()"))
    public = replace(target, import_path="nsgablack.representation:ContextGaussianMutation")
    assert groups(build_assembly_neighbor_sections(internal, candidates=[public]))["assembly_uses"][0]["key"] == target.key
    assert groups(build_assembly_neighbor_sections(internal, candidates=[public]))["assembly_uses"][0]["evidence"][0]["target_reexports"]
    module_import = replace(owner, minimal_wiring=("from nsgablack import representation as ops", "ops.ContextGaussianMutation()"))
    assert groups(build_assembly_neighbor_sections(module_import, candidates=[target]))["assembly_uses"][0]["key"] == target.key


def test_unicode_columns_count_text_characters_in_original_snippet():
    owner = component("owner", "demo:Owner", "from right import Widget", "结果 = Widget()")
    evidence = groups(build_assembly_neighbor_sections(owner, candidates=[component("target", "right:Widget")]))["assembly_uses"][0]["evidence"][0]
    assert evidence["column"] == 6 and evidence["end_column"] == 14


def test_reexport_cycles_and_conflicting_aliases_are_not_equated(tmp_path, monkeypatch):
    from nsgablack.catalog import assembly_relations
    package = tmp_path / "nsgablack"
    package.mkdir()
    (package / "__init__.py").write_text("from .other import Widget\n", encoding="utf-8")
    (package / "other.py").write_text("from . import Widget\n", encoding="utf-8")
    monkeypatch.setattr(assembly_relations, "_package_roots", lambda: {"nsgablack": package})
    owner = component("owner", "demo:Owner", "from nsgablack import Widget", "Widget()")
    target = component("target", "nsgablack.other:Widget")
    assert not groups(build_assembly_neighbor_sections(owner, candidates=[target]))
    (package / "__init__.py").write_text("from .other import Widget\nfrom .extra import Widget\n", encoding="utf-8")
    assert not groups(build_assembly_neighbor_sections(owner, candidates=[target]))


def _source_fixture(monkeypatch, entries):
    catalog = Catalog(entries, details_resolved=True)
    monkeypatch.setattr(facade, "get_source_catalog", lambda **kwargs: catalog)
    return catalog


def test_facade_source_preserves_contract_and_companion_relations(monkeypatch):
    owner = component("owner", "demo:Owner", "from right import Widget", "Widget()",
                      companions=("target",), context_provides=("mutation_sigma",))
    target = component("target", "right:Widget", context_requires=("mutation_sigma",))
    _source_fixture(monkeypatch, [owner, target])
    payload = facade.catalog_neighbors("owner", source_mode="off")
    assert payload["companions"][0]["key"] == "target"
    assert groups(payload)["context_provides::mutation_sigma"][0]["key"] == "target"
    assert groups(payload)["assembly_uses"][0]["key"] == "target"
    assert any(card["family"] == "assembly" for card in payload["relation_cards"])
    assert any(card["family"] == "context" for card in payload["relation_cards"])


@pytest.mark.parametrize("backend", ["mysql", "postgres-legacy", "postgres-surface"])
def test_published_database_and_source_compute_identical_evidence(backend, monkeypatch):
    owner = component("owner", "demo:Owner", "from right import Widget as Build", "def make():", "", "    return Build()")
    target = component("target", "right:Widget")
    entries = [owner, target]
    _source_fixture(monkeypatch, entries)
    expected = facade.catalog_neighbors("target", source_mode="off")
    source_bundle = CatalogBundle(
        components=tuple(_build_component(entry) for entry in entries),
        contexts=tuple(_build_context_contract(entry) for entry in entries),
        usages=tuple(UsageContract(component_key=entry.key, minimal_wiring=entry.minimal_wiring,
                                  use_when=(), required_companions=(), config_keys=(), example_entry="") for entry in entries),
        params=(), methods=(), health=(),
    )
    store = MySQLCatalogStore("mysql://local/local") if backend == "mysql" else PostgresCatalogStore("postgresql://local/local")
    connection = LocalConnection(mapping_rows=backend != "mysql")
    try:
        if backend == "postgres-surface":
            store._materialize_surface_catalog(connection, source_bundle, profile="default")
            restored = store._surface_entries_from_query(connection, profile="default")
        else:
            materialize_legacy(store, connection, source_bundle)
            restored = store._catalog_entries_from_query(connection, profile="default")
        restored_by_key = {entry.key: entry for entry in restored}
        assert restored_by_key["owner"].minimal_wiring == owner.minimal_wiring
        database = SimpleNamespace(
            neighbor_payload=lambda key, **kwargs: {"key": key, "companions": [], "linked_by": []},
            get_catalog_entry=lambda key, **kwargs: restored_by_key.get(key),
            list_catalog_entries=lambda **kwargs: restored,
        )
        monkeypatch.setattr(facade, "_resolve_read_route", lambda **kwargs: facade.CatalogReadRoute(
            profile="default", source_mode="only", effective_source=backend, db_store=database))
        actual = facade.catalog_neighbors("target", source_mode="only")
        assert groups(actual)["assembly_used_by"] == groups(expected)["assembly_used_by"]
        assert actual["assembly_status"] == expected["assembly_status"]
    finally:
        connection.native.close()


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_real_vns_sa_usage_links_are_bidirectional_within_profile(profile):
    catalog = get_source_catalog(profile=profile)
    target = catalog.get("repr.context_gaussian")
    selected = [catalog.get(key) for key in ("adapter.vns", "adapter.sa", "repr.context_gaussian")]
    assert all(selected)
    payload = build_assembly_neighbor_sections(target, candidates=selected)
    assert {row["key"] for row in groups(payload)["assembly_used_by"]} == {"adapter.vns", "adapter.sa"}
    for row in groups(payload)["assembly_used_by"]:
        assert row["evidence"][0]["resolution"] == "static-reexport"


@pytest.mark.parametrize("backend", ["source", "database"])
def test_profile_boundary_does_not_reintroduce_default_only_targets(monkeypatch, backend):
    owner = component("owner", "demo:Owner", "from nsgablack.hidden import Widget", "Widget()")
    hidden = replace(component("example.hidden", "nsgablack.hidden:Widget"), kind="example")
    monkeypatch.setattr(facade, "get_source_catalog", lambda **kwargs: Catalog(
        [owner, hidden] if kwargs.get("profile") == "default" else [owner], details_resolved=True))
    if backend == "database":
        database = SimpleNamespace(
            neighbor_payload=lambda key, **kwargs: {"key": key, "companions": [], "linked_by": []},
            get_catalog_entry=lambda key, **kwargs: owner if key == owner.key else None,
            list_catalog_entries=lambda **kwargs: [owner, hidden] if kwargs.get("profile") == "default" else [owner],
        )
        monkeypatch.setattr(facade, "_resolve_read_route", lambda **kwargs: facade.CatalogReadRoute(
            profile=kwargs.get("profile") or "default", source_mode="only", effective_source="database", db_store=database))
    assert groups(facade.catalog_neighbors("owner", profile="default", source_mode="off"))["assembly_uses"]
    core = facade.catalog_neighbors("owner", profile="framework-core", source_mode="off")
    assert "assembly_uses" not in groups(core)
    assert "example.hidden" not in repr(core)
    assert core["assembly_diagnostics"][0]["code"] == "unresolved-target"


@pytest.fixture
def focused_usage(tmp_path, monkeypatch):
    from nsgablack.catalog import assembly_relations
    from nsgablack.catalog.examples import build_example_index

    root = tmp_path / "nsgablack"
    (root / "catalog/example_manifests").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "pyproject.toml").write_text('[project]\nname="fixture"\n', encoding="utf-8")
    source = root / "docs/usage.md"
    source.write_text("# Guide\n\n## owner Assembly\n\n```python\nfrom right import Widget as Build\nBuild()\n```\n\n## unrelated\ntext\n", encoding="utf-8")
    manifest = root / "catalog/example_manifests/usage.toml"
    manifest.write_text('[[example]]\nid="owner.usage"\ncomponent_keys=["owner"]\nkind="documentation"\n'
                        'sources=[{path="nsgablack/docs/usage.md", section="owner"}, {path="nsgablack/docs/usage.md", section="owner"}]\n'
                        '[[example]]\nid="owner.second"\ncomponent_keys=["owner"]\nkind="documentation"\n'
                        'sources=[{path="nsgablack/docs/usage.md", section="owner"}]\n', encoding="utf-8")
    index_path = tmp_path / "index.json"
    build_example_index({"nsgablack": root}, index_path,
                        catalog_entries=[{"key": "owner"}, {"key": "declared", "example_entry": "docs/usage.md"}])
    monkeypatch.setenv("NSGABLACK_CATALOG_EXAMPLES_INDEX", str(index_path))
    monkeypatch.setattr(assembly_relations, "_package_roots", lambda: {"nsgablack": root})
    return source, index_path


def test_focused_source_checked_documentation_has_real_lines_and_deduplicated_evidence(focused_usage, monkeypatch):
    from nsgablack.catalog import examples

    original_read = examples._read
    reads = []
    splits = []

    class CountedSource(str):
        def splitlines(self, *args, **kwargs):
            splits.append(1)
            return super().splitlines(*args, **kwargs)

    def read_source(roots, qualified):
        reads.append(qualified)
        text, digest = original_read(roots, qualified)
        return CountedSource(text), digest

    monkeypatch.setattr(examples, "_read", read_source)
    owner, target = component("owner", "demo:Owner"), component("target", "right:Widget")
    payload = build_assembly_neighbor_sections(owner, candidates=[target])
    assert payload["assembly_status"] == "analyzed"
    evidence, = groups(payload)["assembly_uses"][0]["evidence"]
    assert evidence["source_field"] == "usage_example"
    assert evidence["source_path"] == "nsgablack/docs/usage.md"
    assert evidence["line"] == 7 and evidence["import_line"] == 6
    assert evidence["example_ids"] == ("owner.second", "owner.usage")
    assert len(evidence["file_sha256"]) == 64
    # Three focused excerpts of one file share a single source line split.
    assert len(splits) == 1
    reverse = build_assembly_neighbor_sections(target, candidates=[owner])
    assert groups(reverse)["assembly_used_by"][0]["evidence"] == (evidence,)
    assert reads == ["nsgablack/docs/usage.md"]
    assert len(splits) == 2  # One split in each independent neighbor request.
    declared = component("declared", "demo:Declared")
    assert not groups(build_assembly_neighbor_sections(declared, candidates=[target]))


def test_stale_or_invalid_usage_index_keeps_existing_wiring_relations(focused_usage):
    source, index_path = focused_usage
    owner = component("owner", "demo:Owner", "from left import Legacy", "Legacy()")
    legacy, target = component("legacy", "left:Legacy"), component("target", "right:Widget")
    initial = build_assembly_neighbor_sections(owner, candidates=[legacy, target])
    assert {row["key"] for row in groups(initial)["assembly_uses"]} == {"legacy", "target"}
    source.write_text(source.read_text(encoding="utf-8") + "\nchanged source\n", encoding="utf-8")
    payload = build_assembly_neighbor_sections(owner, candidates=[legacy, target])
    assert [row["key"] for row in groups(payload)["assembly_uses"]] == ["legacy"]
    assert any(item["code"] == "usage-source-unavailable" for item in payload["assembly_diagnostics"])
    index_path.write_text("{broken", encoding="utf-8")
    payload = build_assembly_neighbor_sections(owner, candidates=[legacy, target])
    assert [row["key"] for row in groups(payload)["assembly_uses"]] == ["legacy"]
    assert any(item["code"] == "usage-index-invalid" for item in payload["assembly_diagnostics"])


def test_focused_documentation_cannot_reintroduce_an_out_of_scope_target(focused_usage):
    owner = component("owner", "demo:Owner")
    payload = build_assembly_neighbor_sections(owner)
    assert not groups(payload)
    assert "target" not in {row["key"] for values in groups(payload).values() for row in values}


def test_documentation_blocks_keep_independent_import_scopes():
    from nsgablack.catalog.assembly_relations import _python_blocks

    text = "```python\nfrom right import Widget\n```\n```py\nWidget()\n```\n```javascript\nWidget()\n```\n```python\nWidget()"
    assert _python_blocks(text) == ((2, ("from right import Widget",)), (5, ("Widget()",)))
