"""API evidence is derived from source, not name heuristics or live objects."""
from copy import deepcopy
import hashlib
from pathlib import Path

import pytest

from nsgablack.catalog import lab_api as api


def test_shared_candidate_return_type_can_be_inspected_at_its_real_owner():
    result = api.inspect_framework_api("blackbase.types.CandidateBatch", member="numeric_matrix")
    assert result["status"] == "found" and result["member_status"] == "found"
    assert result["symbol"] == "blackbase.types.CandidateBatch"
    assert result["source"]["path"] == "@blackbase/types.py"
    assert result["member"]["annotation"] == "np.ndarray"
    assert "__iter__" not in result["member_names"]
    api.verify_api_sources(result)
    assert api.inspect_framework_api("CandidateBatch")["symbol"] == result["symbol"]


def test_shared_source_lookup_does_not_import_dependency_or_accept_arbitrary_files(tmp_path, monkeypatch):
    from types import SimpleNamespace
    package = tmp_path / "shared"
    package.mkdir()
    (package / "__init__.py").write_text("raise RuntimeError('must not import')\n", encoding="utf-8")
    path = package / "types.py"
    path.write_text("class SharedEnvelope:\n    value: int = 2\n", encoding="utf-8")
    monkeypatch.setattr(api, "find_spec", lambda name: SimpleNamespace(origin=str(package / "__init__.py")))
    result = api.inspect_framework_api("blackbase.types.SharedEnvelope", member="value")
    assert result["member"]["annotation"] == "int"
    api.verify_api_sources(result)
    path.write_text("class SharedEnvelope:\n    value: float = 2.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="api_source_changed"):
        api.verify_api_sources(result)
    for target in ("@blackbase/../secrets.json", "@blackbase/resources/model.py", "@blackbase/__init__.py"):
        with pytest.raises(ValueError, match="api_source_refused"):
            api._read(target)


def test_actual_pool_types_have_different_interfaces():
    raw = api.inspect_framework_api("SolutionPool", member="subpool")
    assert raw["status"] == "found" and raw["member_status"] == "not_declared"
    assert raw["symbol"] == "nsgablack.core.state.solution_pool.SolutionPool"
    assert raw["members_complete"]
    assert "subpool_refs" in raw["member_names"]
    assert api.lookup_api_member(raw, "subpool") is None
    scoped = api.inspect_framework_api("ChangePool", member="subpool")
    assert scoped["member_status"] == "found"
    assert scoped["member"]["signature"] == "subpool(self, name) -> ChangeSelection"
    assert "def subpool" in scoped["member"]["excerpt"]
    assert scoped["source_scope"] == "framework"
    api.verify_api_sources(scoped)


def test_actual_public_pool_alias_resolves_collection_not_access_scope():
    for name in ("Pool", "nsgablack.adapters.Pool", "nsgablack.adapters.change_pool.Pool"):
        result = api.inspect_framework_api(name, member="random")
        assert result["status"] == "found"
        assert result["symbol"] == "nsgablack.adapters.change_pool.ChangeSelection"
        assert result["requested_name"] == name
        assert result["member_status"] == "found"
        assert result["resolution_sources"]
        api.verify_api_sources(result)
    wrong_receiver = api.inspect_framework_api("Pool", member="subpool_refs")
    assert wrong_receiver["member_status"] == "not_declared"
    assert "random" in wrong_receiver["member_names"]
    assert "read" not in wrong_receiver["member_names"]


def test_actual_selector_signature_preserves_keyword_only_arguments():
    result = api.inspect_framework_api("nsgablack.adapters.parent_selection.MixedPoolParentSelector", member="select")
    method = api.lookup_api_member(result, "select")
    assert method["bound"] and method["kind"] == "method"
    assert [(row["name"], row["kind"], row["required"]) for row in method["parameters"]] == [
        ("self", "positional_or_keyword", True), ("request", "positional_or_keyword", True),
        ("pool", "keyword_only", True), ("rng", "keyword_only", True)]
    assert method["parameters"][1]["annotation"] == "ParentSelectionRequest"


def test_actual_decomposition_fields_are_not_config_fields():
    config = api.inspect_framework_api("MOEADConfig", member="nr")
    assert config["member"]["kind"] == "declared_field"
    assert config["member"]["annotation"] == "int"
    assert config["member"]["default"] == "2"
    unit = api.inspect_framework_api("DecompositionUnit", member="nr")
    assert "nr" not in unit["member_names"]
    assert "population" in unit["member_names"] and "weights" in unit["member_names"]
    # Its inherited generic setattr cannot be treated as proof of runtime absence.
    assert unit["dynamic_attributes"] and unit["member_status"] == "unknown"
    assert unit["declared_member_status"] == "not_declared"
    assert {row["path"] for row in unit["sources"]} >= {"units/collections.py", "units/features.py"}


def test_project_source_property_exposes_actual_body_without_running_it():
    path = Path(__file__).parents[1] / "examples/cases/assembled_ga_vns/cases/hybrid_search/config.py"
    data = path.read_bytes()
    result = api.inspect_python_api(data.decode("utf-8-sig"), "DemoConfig", path="cases/hybrid_search/config.py",
        sha256=hashlib.sha256(data).hexdigest(), member="max_steps")
    assert result["source_scope"] == "provided_source"
    method = result["member"]
    assert method["kind"] == "property"
    assert "self.ga_steps + self.refinement_count * self.local_steps + 1" in method["excerpt"]
    assert "self.rounds * work + 1" in method["excerpt"]
    assert result["source"]["sha256"] == hashlib.sha256(data).hexdigest()
    with pytest.raises(ValueError, match="api_evidence_invalid"):
        api.verify_api_sources(result)


@pytest.fixture
def sources(tmp_path, monkeypatch):
    directory = tmp_path / "adapters"
    directory.mkdir()
    monkeypatch.setattr(api, "_ROOT", tmp_path)

    def write(name, content):
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path
    return write


def test_resolution_reexports_relative_imports_and_inheritance_without_import(sources):
    sources("base.py", "raise RuntimeError('module must not execute')\nclass Base:\n    flag: bool = True\n    def read(self, /, count=1, *, strict=False): return count\n")
    sources("__init__.py", "from .base import Base as Public\n")
    sources("child.py", "from . import Public\nclass Child(Public):\n    def write(self, *values, **options): pass\n")
    result = api.inspect_framework_api("nsgablack.adapters.child.Child", member="read")
    assert result["members_complete"] and "flag" in result["member_names"]
    assert result["member"]["owner"] == "nsgablack.adapters.base.Base"
    assert [row["kind"] for row in result["member"]["parameters"]] == ["positional_only", "positional_or_keyword", "keyword_only"]
    assert result["member"]["parameters"][1]["default"] == "1"
    alias = api.inspect_framework_api("nsgablack.adapters.Public")
    assert alias["symbol"] == "nsgablack.adapters.base.Base"
    variadic = api.inspect_framework_api("Child", member="write")
    assert [row["kind"] for row in variadic["member"]["parameters"]][-2:] == ["var_positional", "var_keyword"]


def test_ambiguous_symbol_returns_candidates_without_guessing(sources):
    sources("one.py", "class Repeated: pass\n")
    sources("two.py", "class Repeated: pass\n")
    result = api.inspect_framework_api("Repeated")
    assert result["status"] == "ambiguous" and len(result["candidates"]) == 2
    assert "symbol" not in result
    assert api.inspect_framework_api("Missing")["status"] == "not_found"


def test_simple_alias_chains_deduplicate_exports_but_not_different_destinations(sources):
    sources("source.py", "class First: pass\nclass Other: pass\nPool = First\nSecond = Pool\n")
    sources("__init__.py", "from .source import Second as Pool\n")
    result = api.inspect_framework_api("Pool")
    assert result["status"] == "found"
    assert result["symbol"] == "nsgablack.adapters.source.First"
    result = api.inspect_framework_api("nsgablack.adapters.Pool")
    assert {row["path"] for row in result["sources"]} == {"adapters/__init__.py", "adapters/source.py"}
    sources("different.py", "from .source import Other\nPool = Other\n")
    ambiguous = api.inspect_framework_api("Pool")
    assert ambiguous["status"] == "ambiguous" and len(ambiguous["candidates"]) == 2


def test_alias_chain_source_changes_invalidate_evidence(sources):
    sources("source.py", "class First: pass\nclass Other: pass\n")
    path = sources("__init__.py", "from .source import First as Public\n")
    result = api.inspect_framework_api("nsgablack.adapters.Public")
    api.verify_api_sources(result)
    path.write_text("from .source import Other as Public\n", encoding="utf-8")
    with pytest.raises(ValueError, match="api_source_changed"):
        api.verify_api_sources(result)
    assert api.inspect_framework_api("nsgablack.adapters.Public")["symbol"].endswith(".Other")


def test_alias_resolution_never_calls_factory_or_guesses_rebound_names(sources):
    sources("factory.py", "class Original: pass\nAlias = Original\nOriginal = unknown_factory()\nDynamic = unknown_factory()\n")
    assert api.inspect_framework_api("Dynamic")["status"] == "not_found"
    assert api.inspect_framework_api("Alias")["status"] == "not_found"


def test_missing_members_of_dynamic_or_external_base_remain_unknown(sources):
    sources("dynamic.py", "from external import Base\nclass External(Base): pass\nclass Dynamic:\n    def __getattr__(self, name): return name\nclass Meta(metaclass=Factory): pass\n")
    for symbol in ("External", "Dynamic", "Meta"):
        result = api.inspect_framework_api(symbol, member="guess")
        assert not result["members_complete"] and result["member_status"] == "unknown"


def test_static_classmethod_and_observed_instance_fields(sources):
    sources("named.py", "class Item:\n    def __init__(self, *, size=2): self.size = size\n    @staticmethod\n    def make(value): return value\n    @classmethod\n    def restore(cls, state): return state\n")
    result = api.inspect_framework_api("Item")
    assert result["constructor_status"] == "explicit"
    assert api.lookup_api_member(result, "size")["kind"] == "instance_assignment"
    assert not api.lookup_api_member(result, "make")["bound"]
    assert api.lookup_api_member(result, "restore")["bound"]


def test_generated_dataclass_constructor_does_not_reuse_wrong_base_signature(sources):
    sources("generated.py", "from dataclasses import dataclass\nclass Base:\n    def __init__(self, old): pass\n@dataclass\nclass Child(Base):\n    changed: int = 2\n")
    result = api.inspect_framework_api("Child", member="__init__")
    assert result["constructor_status"] == "generated_unresolved"
    assert result["member"] is None
    assert "changed" in result["member_names"]


def test_evidence_hash_rejects_source_changes_and_refuses_outside_paths(sources):
    path = sources("entry.py", "class Entry:\n    value: int = 2\n")
    result = api.inspect_framework_api("Entry")
    api.verify_api_sources(result)
    path.write_text("class Entry:\n    value: int = 3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="api_source_changed"):
        api.verify_api_sources(result)
    forged = deepcopy(result)
    forged["sources"][0]["path"] = "../private.py"
    with pytest.raises(ValueError, match="api_source_refused"):
        api.verify_api_sources(forged)


def test_parse_cache_uses_current_content_not_only_path_or_timestamp(sources):
    import os
    path = sources("cached.py", "class Cached:\n    value: int = 2\n")
    original = path.stat()
    initial = api.inspect_framework_api("Cached", member="value")
    hits = api._parsed_module.cache_info().hits
    again = api.inspect_framework_api("Cached", member="value")
    assert again == initial and api._parsed_module.cache_info().hits > hits
    path.write_text("class Cached:\n    value: int = 3\n", encoding="utf-8")
    os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
    changed = api.inspect_framework_api("Cached", member="value")
    assert changed["member"]["default"] == "3"
    assert changed["source"]["sha256"] != initial["source"]["sha256"]
    assert api._parsed_module.cache_info().maxsize == 512


def test_links_and_example_templates_are_excluded(sources, tmp_path):
    outside = tmp_path / "outside.py"
    outside.write_text("class Private: pass\n", encoding="utf-8")
    sources("scaffold/copy.py", "class Copied: pass\n")
    assert api.inspect_framework_api("Copied")["status"] == "not_found"
    link = tmp_path / "adapters/linked.py"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Windows account cannot create a symbolic link")
    assert api.inspect_framework_api("Private")["status"] == "not_found"


@pytest.mark.parametrize("symbol", ["../secrets", "C:/private.py", "__import__('os')", "a\\b", "a..b", "", "a" * 241, None])
def test_lookup_is_a_symbol_not_a_path_or_expression(symbol):
    with pytest.raises(ValueError, match="api_symbol_invalid"):
        api.inspect_framework_api(symbol)


def test_summary_truncation_does_not_hide_targeted_member_or_names(sources):
    sources("large.py", "class Large:\n" + "".join(f"    def method_{i}(self, value): return value\n" for i in range(90)))
    result = api.inspect_framework_api("Large")
    assert result["details_truncated"] and len(result["methods"]) == 35
    assert result["members_complete"] and len(result["member_names"]) == 90
    targeted = api.inspect_framework_api("Large", member="method_89")
    assert targeted["member_status"] == "found" and "return value" in targeted["member"]["excerpt"]


def test_property_return_inference_follows_constructor_field_and_helper_without_execution(sources):
    helper = sources("helpers.py", "def refs(items):\n    return tuple(items)\n")
    sources("view.py", "from .helpers import refs\nclass Selection:\n    def __init__(self, items):\n        values = refs(items)\n        self._refs = values\n    @property\n    def refs(self):\n        return self._refs\n")
    result = api.inspect_framework_api("Selection", member="refs")
    contract = result["member"]["return_contract"]
    assert contract["kind"] == "builtin" and contract["symbol"] == "builtins.tuple"
    assert {row["path"] for row in result["sources"]} == {"adapters/view.py", "adapters/helpers.py"}
    api.verify_api_sources(result)
    helper.write_text("def refs(items):\n    return list(items)\n", encoding="utf-8")
    with pytest.raises(ValueError, match="api_source_changed"):
        api.verify_api_sources(result)


def test_return_inference_tracks_simple_constructor_and_self_delegation(sources):
    sources("view.py", "class Selection: pass\nclass Reader:\n    def _select(self, items):\n        return Selection()\n    def read(self, items):\n        if items is None:\n            raise ValueError('missing')\n        return self._select(items)\n")
    result = api.inspect_framework_api("Reader", member="read")
    assert result["member"]["return_contract"]["symbol"] == "nsgablack.adapters.view.Selection"
    assert result["member"]["return_contract"]["kind"] == "instance"


@pytest.mark.parametrize("source", [
    "def method(self, condition):\n        if condition: return tuple()\n        return list()",
    "def method(self, condition):\n        if condition: return tuple()",
    "def method(self):\n        return self.method()",
    "def method(self, tuple):\n        return tuple()",
    "def method(self):\n        result = tuple()\n        tuple = factory\n        return result",
    "def method(self):\n        return factory()",
    "@wrapper\n    def method(self):\n        return tuple()",
    "async def method(self):\n        return tuple()",
])
def test_return_inference_keeps_ambiguous_dynamic_shadowed_or_wrapped_values_unknown(sources, source):
    sources("unknown.py", "class Unknown:\n    " + source + "\n")
    result = api.inspect_framework_api("Unknown", member="method")
    assert result["member"]["return_contract"]["kind"] == "unknown"


def test_actual_refs_property_has_a_sourced_noncallable_return_contract():
    result = api.inspect_framework_api("ChangeSelection", member="refs")
    assert result["member"]["return_contract"]["symbol"] == "builtins.tuple"
    assert result["member"]["return_contract"]["sources"]
    api.verify_api_sources(result)


@pytest.mark.parametrize("name", ["read", "subpool", "_selection"])
def test_real_change_pool_return_annotations_identify_selection_instead_of_numeric_values(name):
    result = api.inspect_framework_api("ChangePool", member=name)
    assert result["member"]["returns"] == "ChangeSelection"
    api.verify_api_sources(result)


def test_custom_allocation_and_ambiguous_field_storage_do_not_invent_types(sources):
    sources("custom.py", "class Allocated:\n    def __new__(cls): return foreign\nclass Factory:\n    def make(self): return Allocated()\nclass Fields:\n    def __init__(self, condition):\n        if condition: self._refs=tuple()\n        else: self._refs=list()\n    @property\n    def refs(self): return self._refs\n")
    for symbol, member in (("Factory", "make"), ("Fields", "refs")):
        assert api.inspect_framework_api(symbol, member=member)["member"]["return_contract"]["kind"] == "unknown"


def test_focused_population_schema_exposes_its_real_factory_type_declaration():
    result = api.inspect_framework_api("PopulationUnit", member="schema")
    value = result["member"]["value_contract"]
    assert value["symbol"] == "nsgablack.units.contracts.UnitSchema"
    assert value["factory"] == "nsgablack.units.collections.structure_schema"
    assert value["basis"] == "declared_factory_return_annotation"
    assert value["runtime_validated"] is False
    assert {row["path"] for row in value["sources"]} == {"units/collections.py", "units/contracts.py"}
    assert api.lookup_api_member(result, "schema")["value_contract"] == value
    api.verify_api_sources(result)


def test_unrelated_factory_annotation_is_source_bound_not_a_live_value(sources):
    definition = sources("descriptor.py", "class Descriptor: pass\n")
    factory = sources("factory.py", "from .descriptor import Descriptor as D\ndef make() -> 'D':\n    raise RuntimeError('must never execute')\n")
    sources("holder.py", "from .factory import make as construct\nclass Holder:\n    item = construct()\n")
    result = api.inspect_framework_api("Holder", member="item")
    value = result["member"]["value_contract"]
    assert value["symbol"] == "nsgablack.adapters.descriptor.Descriptor"
    assert value["basis"] == "declared_factory_return_annotation" and not value["runtime_validated"]
    assert {row["path"] for row in result["sources"]} >= {"adapters/factory.py", "adapters/descriptor.py"}
    api.verify_api_sources(result)
    factory.write_text(factory.read_text(encoding="utf-8").replace("'D'", "Unknown"), encoding="utf-8")
    with pytest.raises(ValueError, match="api_source_changed"):
        api.verify_api_sources(result)
    assert definition.is_file()


@pytest.mark.parametrize("factory,initializer", [
    ("def make(): return Descriptor()", "make()"),
    ("def make() -> Descriptor | None: return None", "make()"),
    ("@wrapper\ndef make() -> Descriptor: return Descriptor()", "make()"),
    ("async def make() -> Descriptor: return Descriptor()", "make()"),
    ("def make() -> Descriptor: return Descriptor()", "registry[name]()"),
    ("def make() -> Descriptor: return Descriptor()", "make() if condition else foreign"),
])
def test_field_value_contract_does_not_guess_dynamic_or_ambiguous_factory_results(sources, factory, initializer):
    sources("holder.py", "class Descriptor: pass\n" + factory + "\nclass Holder:\n    item=" + initializer + "\n")
    value = api.inspect_framework_api("Holder", member="item")["member"]["value_contract"]
    assert value["kind"] == "unknown" and "symbol" not in value and not value["runtime_validated"]


def test_class_local_factory_shadow_does_not_reuse_module_annotation(sources):
    sources("holder.py", "class Descriptor: pass\ndef make() -> Descriptor: return Descriptor()\nclass Holder:\n    make=foreign_factory\n    item=make()\n")
    value = api.inspect_framework_api("Holder", member="item")["member"]["value_contract"]
    assert value["kind"] == "unknown" and "symbol" not in value
