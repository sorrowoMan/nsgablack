"""Exercise the exact copyable ML snippets published in component details.

These are component/assembly checks, not Project training receipts. External
data sources and the explicitly dependency-bound statsmodels fit stay static.
"""
from __future__ import annotations

import ast
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import re
try:
    import tomllib
except ImportError:  # Python 3.10
    import tomli as tomllib

import pytest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "catalog/example_manifests/mlblack_usage.toml"
RECORDS = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))["example"]
STATIC_KEYS = {
    "mlblack.model.statsmodels_sarimax_forecast",
    "mlblack.pipeline.hive_query_source", "mlblack.pipeline.source.hive_query",
    "mlblack.pipeline.jdbc_query_source", "mlblack.pipeline.source.jdbc_query",
    "mlblack.pipeline.s3_parquet_source", "mlblack.pipeline.source.s3_parquet",
}


def source_code(record):
    source = record["sources"][0]
    assert source["path"] == "nsgablack/docs/catalog_usage/MLBLACK_COMPONENT_USAGE_CN.md"
    document = ROOT / source["path"].removeprefix("nsgablack/")
    from nsgablack.catalog.examples import _snippet

    assert document.is_file()
    excerpt = _snippet({"nsgablack": ROOT}, source)["text"]
    blocks = re.findall(r"```python\n(.*?)\n```", excerpt, flags=re.DOTALL)
    assert len(blocks) == 1
    assert all(key in excerpt for key in record["component_keys"])
    return blocks[0]


@pytest.mark.parametrize("record", RECORDS, ids=lambda record: record["id"])
def test_ml_usage_matches_real_component_api_without_training(record):
    code = source_code(record)
    ast.parse(code)
    assert record["inputs"] and record["steps"] and record["dependencies"] and record["expected_outputs"]
    if set(record["component_keys"]) & STATIC_KEYS:
        # Parsing is useful here; it is not permission to connect to a sample
        # hostname or invoke an optional third-party fitting backend.
        return
    pytest.importorskip("mlblack")
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        exec(compile(code, record["id"], "exec"), {"__name__": "catalog_component_example"})
