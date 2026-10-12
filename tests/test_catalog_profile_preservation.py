from dataclasses import asdict, replace

import pytest

from nsgablack.catalog.registry import CatalogEntry, _apply_catalog_profile
from nsgablack.catalog.store.mysql import _apply_profile_to_entry as mysql_profile
from nsgablack.catalog.store.postgres import _apply_profile_to_entry as postgres_profile


@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_profile_policy_is_identical_and_preserves_complete_contract(profile):
    entry = CatalogEntry(
        key="adapter.demo", title="Demo", kind="adapter", import_path="demo:Adapter",
        example_entry="examples/demo.py", artifact_requires=("dataset",),
        artifact_provides=("model",), phase_in=("fit",), phase_out=("ready",),
        contract={"recovery": "exact"}, metadata={"owner": "demo"}, detail_ref="demo.toml",
    )
    expected = replace(entry, example_entry="") if profile == "framework-core" else entry
    for filtered in (_apply_catalog_profile([entry], profile)[0],
                     mysql_profile(entry, profile=profile),
                     postgres_profile(entry, profile=profile)):
        assert asdict(filtered) == asdict(expected)
    assert entry.example_entry == "examples/demo.py"


@pytest.mark.parametrize("kind,path", [("example", "x:y"), ("doc", "x:y"),
                                      ("adapter", "examples/demo.py:Adapter")])
def test_profile_exclusions_match_for_all_backends(kind, path):
    entry = CatalogEntry(key="demo", title="demo", kind=kind, import_path=path)
    assert _apply_catalog_profile([entry], "framework-core") == []
    assert mysql_profile(entry, profile="framework-core") is None
    assert postgres_profile(entry, profile="framework-core") is None
