from __future__ import annotations

import os
from pathlib import Path


def test_catalog_can_load_external_entries_from_env(tmp_path: Path, monkeypatch):
    toml = tmp_path / "extra_catalog.toml"
    toml.write_text(
        """
[[entry]]
key = "bias._test_external"
title = "ExternalBias"
kind = "bias"
import_path = "nsgablack.bias.algorithmic.convergence:ConvergenceBias"
tags = ["external"]
summary = "external entry for tests"
companions = ["bias.convergence"]
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("NSGABLACK_CATALOG_PATH", str(toml))

    from nsgablack.catalog import get_catalog

    c = get_catalog(refresh=True)
    e = c.get("bias._test_external")
    assert e is not None
    assert e.load().__name__ == "ConvergenceBias"

