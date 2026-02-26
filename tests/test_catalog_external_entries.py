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


def test_catalog_can_load_external_entries_from_env_directory(tmp_path: Path, monkeypatch):
    entries_dir = tmp_path / "entries"
    entries_dir.mkdir(parents=True, exist_ok=True)
    (entries_dir / "bias_part.toml").write_text(
        """
[[entry]]
key = "bias._test_external_dir"
title = "ExternalBiasDir"
kind = "bias"
import_path = "nsgablack.bias.algorithmic.convergence:ConvergenceBias"
tags = ["external", "dir"]
summary = "external entry from directory"
companions = ["bias.convergence"]
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("NSGABLACK_CATALOG_PATH", str(entries_dir))

    from nsgablack.catalog import get_catalog

    c = get_catalog(refresh=True)
    e = c.get("bias._test_external_dir")
    assert e is not None
    assert e.load().__name__ == "ConvergenceBias"


def test_catalog_index_detail_split_loads_details_on_demand(tmp_path: Path, monkeypatch):
    entries_dir = tmp_path / "entries_split"
    entries_dir.mkdir(parents=True, exist_ok=True)
    (entries_dir / "entry_index.toml").write_text(
        """
[[entry]]
key = "bias._split_detail"
title = "SplitDetailBias"
kind = "bias"
import_path = "nsgablack.bias.algorithmic.convergence:ConvergenceBias"
tags = ["split", "detail"]
summary = "index summary"
details_file = "entry_detail.toml"
""".strip(),
        encoding="utf-8",
    )
    (entries_dir / "entry_detail.toml").write_text(
        """
[detail]
summary = "hydrated summary"
use_when = ["for split detail test"]
context_requires = ["generation"]
example_entry = "examples/split_detail_demo.py:build_solver"
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("NSGABLACK_CATALOG_PATH", str(entries_dir))
    from nsgablack.catalog import get_catalog

    c = get_catalog(refresh=True)
    # list/search index should work without forcing full payload.
    found = [x for x in c.search("split detail", fields="all", limit=10) if x.key == "bias._split_detail"]
    assert found
    # on-demand get should hydrate detail payload.
    e = c.get("bias._split_detail")
    assert e is not None
    assert e.summary == "hydrated summary"
    assert "for split detail test" in tuple(e.use_when)
    assert "generation" in tuple(e.context_requires)
