"""Build fixed demonstration evidence offline, before starting a Catalog reader.

Generated indexes and receipts are derived artifacts; the release manifest hashes
the scripts and source inputs. Its identity is then embedded in every receipt.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def main():
    from nsgablack.catalog.examples import build_example_index, load_example_index
    from nsgablack.catalog.curate import build_sources
    from nsgablack.catalog.registry import get_catalog
    from nsgablack.catalog.example_audit import audit_usage

    base = Path("/opt/catalog")
    publication = json.loads((base / "release-manifest.json").read_text())["content_sha256"]
    roots = {name: Path("/opt/src") / name for name in ("nsgablack", "blackbase", "mlblack")}
    index_path, receipts_path = base / "examples.json", base / "example-receipts.json"
    entries = tuple(get_catalog(profile="default").list())
    before = build_example_index(roots, index_path, publication_digest=publication, catalog_entries=entries)
    subprocess.run([sys.executable, str(base / "run_example_receipts.py"),
                    *[argument for name, root in roots.items() for argument in ("--root", f"{name}={root}")],
                    "--index", str(index_path), "--output", str(receipts_path)], check=True)
    after = build_example_index(roots, index_path, receipts_path, publication_digest=publication, catalog_entries=entries)
    index = load_example_index(index_path)
    coverage = audit_usage(index, entries)
    (base / "example-audit.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2))
    if not coverage["complete_usage"]:
        missing = [row["key"] for row in coverage["rows"] if row["quality"] != "usage_recipe"]
        raise RuntimeError("Published Catalog components need explicit usage recipes: " + ", ".join(missing))
    required = {"pool-workflow-ga", "pool-workflow-vns", "pool-workflow-moead", "ml-linear-point",
                "fixed-candidate-project"}
    executed = {key for key, example in index["examples"].items()
                if example["verification"]["status"] == "executed"}
    if not required <= executed:
        raise RuntimeError("Representative demonstrations did not produce matching execution receipts")
    knowledge = build_sources(roots, base / "knowledge-sources.json", base / "knowledge-packets.json",
                              examples_index=index)
    result = {"ok": True, "publication_digest": publication, "before": before, "after": after,
              "executed": sorted(executed), "knowledge": knowledge, "model_calls": 0,
              "usage_coverage": coverage["counts"]}
    (base / "examples-build.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
