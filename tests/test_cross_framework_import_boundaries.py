from __future__ import annotations

from pathlib import Path


def test_rag_uses_public_cross_framework_catalog_surfaces() -> None:
    root = Path(__file__).resolve().parents[1] / "nsgablack" / "rag"
    config_source = (root / "config.py").read_text(encoding="utf-8")
    indexer_source = (root / "indexer.py").read_text(encoding="utf-8")
    package_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(root.glob("*.py"))
    )

    assert "mlblack.catalog.store" not in config_source
    assert "_resolve_postgres" not in config_source
    assert "._entries" not in indexer_source
    assert "sys.path.insert" not in package_source
