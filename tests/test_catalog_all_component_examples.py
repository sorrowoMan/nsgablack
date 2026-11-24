"""Every published component shows its source-bound usage and known gaps.

This tests the whole discovery/display path without running any component.
Actual component calls and formal Project receipts have separate checks.
"""
from pathlib import Path
import os
import re

import pytest

from nsgablack.catalog.example_audit import audit_usage
from nsgablack.catalog.examples import build_example_index, load_example_index


ROOT = Path(__file__).resolve().parents[1]


class Display:
    def __init__(self):
        self.text = []
    def markdown(self, value, **kwargs):
        assert kwargs.get("unsafe_allow_html") is False
        self.text.append(value)
    def code(self, value, **_kwargs):
        self.text.append(value)
    def caption(self, value):
        self.text.append(value)
    def info(self, value):
        self.text.append(value)
    def expander(self, *_args, **_kwargs):
        return self
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        return False


def test_every_federated_component_has_visible_usage_or_explicit_instruction_gaps(tmp_path, monkeypatch):
    from nsgablack.catalog import examples_ui
    from nsgablack.catalog.registry import get_catalog
    from nsgablack.core.blank_solver import SolverBase
    from nsgablack.units import UnitBinding
    from nsgablack.catalog.curation_provider import DeepSeekGenerator

    pytest.importorskip("mlblack")
    roots = {name: ROOT.parent / name for name in ("nsgablack", "blackbase", "mlblack")}
    if not all(path.is_dir() for path in roots.values()):
        pytest.skip("Full source/display audit requires the three trusted repository roots")
    original_providers = os.environ.get("NSGABLACK_CATALOG_PROVIDERS")
    monkeypatch.setenv("NSGABLACK_CATALOG_PROVIDERS", "mlblack=mlblack.catalog.registry:get_catalog")
    entries = tuple(get_catalog(profile="default", refresh=True).list())
    index_path = tmp_path / "examples.json"
    build_example_index(roots, index_path, catalog_entries=entries)
    index = load_example_index(index_path)
    audit = audit_usage(index, entries)
    missing = [row for row in audit["rows"] if row["quality"] != "usage_recipe"]
    assert not missing, missing
    assert set(index["entries"]) == {entry.key for entry in entries}

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Example display must not run a model, Unit or Solver")
    monkeypatch.setattr(SolverBase, "run", forbidden)
    monkeypatch.setattr(UnitBinding, "build", forbidden)
    monkeypatch.setattr(DeepSeekGenerator, "generate", forbidden)
    monkeypatch.setenv(examples_ui.INDEX_ENV, str(index_path))
    examples_ui._load_snapshot.cache_clear()
    try:
        for entry in entries:
            display = Display()
            examples_ui.render_examples(display, entry.as_dict())
            content = "\n".join(display.text)
            assert any(label in content for label in ("输入与准备", "片段里的对象从哪里来", "输入说明待补充")), entry.key
            assert any(label in content for label in ("预期得到什么", "结果检查说明待补充")), entry.key
            assert "使用步骤" in content and "运行依赖" in content, entry.key
            assert not re.search(r"此组件尚缺使用示例", content), entry.key
            assert examples_ui.example_status(entry.as_dict()) != "待补示例", entry.key
    finally:
        examples_ui._load_snapshot.cache_clear()
        if original_providers is None:
            monkeypatch.delenv("NSGABLACK_CATALOG_PROVIDERS", raising=False)
        else:
            monkeypatch.setenv("NSGABLACK_CATALOG_PROVIDERS", original_providers)
        get_catalog(refresh=True)
