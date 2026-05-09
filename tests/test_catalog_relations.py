from __future__ import annotations

import json
from pathlib import Path

from nsgablack.catalog import build_catalog_relation_bundle, export_catalog_relations


def test_build_catalog_relation_bundle_exposes_companions_and_linked_by():
    bundle = build_catalog_relation_bundle(profile="framework-core", kind="adapter")

    assert bundle["summary"]["total_nodes"] >= 1
    assert bundle["summary"]["context_contract_edges"] >= 1
    assert "artifact_contract_edges" in bundle["summary"]
    assert "phase_contract_edges" in bundle["summary"]
    node_by_key = {item["key"]: item for item in bundle["nodes"]}
    assert "adapter.vns" in node_by_key
    vns = node_by_key["adapter.vns"]
    assert "repr.context_gaussian" in vns["companions"]
    assert "repr.context_switch" in vns["companions"]
    assert vns["out_degree"] >= 2
    assert any(edge["source_key"] == "adapter.vns" for edge in bundle["edges"])
    assert any(
        edge["source_key"] == "adapter.vns"
        and edge["target_key"] == "repr.context_gaussian"
        and edge["relation"] == "context_contract"
        and edge["relation_value"] == "mutation_sigma"
        for edge in bundle["edges"]
    )
    assert bundle["summary"]["relation_key_count"] >= 1
    assert any(
        row["relation_family"] == "context"
        and row["relation_value"] == "mutation_sigma"
        and row["consumer_count"] >= 1
        for row in bundle["relation_keys"]
    )


def test_export_catalog_relations_writes_table_edge_and_dot_files(tmp_path: Path):
    output_base = tmp_path / "framework_core_relations"
    result = export_catalog_relations(
        output_path=output_base,
        formats=("json", "table-csv", "edge-csv", "key-csv", "dot", "mermaid", "family-dot", "family-mermaid"),
        profile="framework-core",
        kind="adapter",
        query="vns",
        source_mode="off",
    )

    written = result["written_files"]
    json_path = Path(written["json"])
    table_path = Path(written["table-csv"])
    edge_path = Path(written["edge-csv"])
    key_path = Path(written["key-csv"])
    dot_path = Path(written["dot"])
    mermaid_path = Path(written["mermaid"])
    family_dot = dict(written["family-dot"])
    family_mermaid = dict(written["family-mermaid"])

    assert json_path.exists()
    assert table_path.exists()
    assert edge_path.exists()
    assert key_path.exists()
    assert dot_path.exists()
    assert mermaid_path.exists()
    assert Path(family_dot["context"]).exists()
    assert Path(family_mermaid["context"]).exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["summary"]["total_nodes"] >= 1
    assert payload["summary"]["context_contract_edges"] >= 1
    assert payload["summary"]["relation_key_count"] >= 1
    assert "adapter.vns" in table_path.read_text(encoding="utf-8")
    assert "source_key" in edge_path.read_text(encoding="utf-8")
    assert "relation_family" in edge_path.read_text(encoding="utf-8")
    assert "relation_value" in key_path.read_text(encoding="utf-8")
    assert "mutation_sigma" in key_path.read_text(encoding="utf-8")
    assert "context_contract" in edge_path.read_text(encoding="utf-8")
    assert "digraph nsgablack_catalog_relations" in dot_path.read_text(encoding="utf-8")
    assert "```mermaid" in mermaid_path.read_text(encoding="utf-8")
    assert "ctx:mutation_sigma" in mermaid_path.read_text(encoding="utf-8")
    assert "ctx:mutation_sigma" in Path(family_dot["context"]).read_text(encoding="utf-8")
    assert "ctx:mutation_sigma" in Path(family_mermaid["context"]).read_text(encoding="utf-8")
