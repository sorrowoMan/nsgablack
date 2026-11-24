"""All twelve formerly main-only cards retain their source-bound extensions."""
from pathlib import Path
import ast

import pytest

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from nsgablack.catalog.examples import _base_record
from nsgablack.catalog.curation_seed import extract_source_guide_seed
from nsgablack.catalog.material_plan import build_material_plan
from nsgablack.catalog.usage_api_validation import inspect_usage_api
from nsgablack.catalog.usage_learning import snippet_parts


ROOT = Path(__file__).resolve().parents[1]
ROOTS = {name: ROOT.parent / name for name in ("nsgablack", "blackbase", "mlblack")}
KEYS = ("adapter.composite", "adapter.nsga2", "adapter.moead", "adapter.vns",
        "bias.callable", "bias.risk", "plugin.monte_carlo_eval", "plugin.pareto_archive",
        "repr.gaussian_mutation", "repr.pipeline", "tool.population_unit", "tool.unit_binding")


@pytest.fixture(scope="module")
def extension_records():
    specs = tomllib.loads((ROOT / "catalog/example_manifests/nsgablack_usage.toml").read_text(encoding="utf-8-sig"))
    by_key = {}
    for spec in specs["example"]:
        covered = set(spec["component_keys"]) & set(KEYS)
        if not covered:
            continue
        record = _base_record(spec, ROOTS, None)
        for key in covered:
            by_key[key] = record
    assert set(by_key) == set(KEYS)
    return by_key


@pytest.mark.parametrize("key", KEYS)
def test_complete_card_has_substantive_extension_and_valid_known_api(extension_records, key):
    record = extension_records[key]
    seed = extract_source_guide_seed((record,))
    assert seed and seed["variants"]
    index = {"entries": {key: [record["id"]]}, "examples": {record["id"]: record}, "issues": []}
    row, = build_material_plan(index)["entries"]
    assert row["category"] == "detailed_with_variants" and not row["gaps"]
    assert all(snippet["complete"] for snippet in record["snippets"])
    assert record["verification"]["status"] == "source_checked"
    code = "\n\n".join(value for snippet in record["snippets"]
                         for kind, value, language in snippet_parts(snippet)
                         if kind == "code" and language == "python")
    ast.parse(code)
    inspection = inspect_usage_api(code, source_roots=ROOTS)
    assert not inspection["issues"], inspection["issues"]


def test_composite_guide_keeps_the_actual_assembly_source_closure(extension_records):
    record = extension_records["adapter.composite"]
    assert all(snippet["path"].endswith(".md") for snippet in record["snippets"])
    source = "nsgablack/examples/cases/catalog_recipes/cases/composite/build_solver.py"
    assert source in record["source_files"]
    assert len(record["source_files"][source]) == 64
    assert record["run_command"] == "python examples/cases/catalog_recipes/run_project.py"
