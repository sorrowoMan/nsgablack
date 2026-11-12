"""The isolated publisher raises old private-config budgets without model calls."""
import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize("configured,expected", [(2048, 12288), (16384, 16384)])
def test_runtime_curate_uses_full_tutorial_budget_and_existing_writer_boundary(monkeypatch, configured, expected):
    from nsgablack.catalog import curate as publisher, curation_provider, curation_store, examples

    path = Path(__file__).resolve().parents[1] / "deployment/catalog/runtime.py"
    spec = importlib.util.spec_from_file_location("catalog_curation_runtime_test", path)
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    monkeypatch.setattr(runtime, "load_mysql_config", lambda _: {
        "host": "localhost", "port": 3306, "database": "fixture", "user": "fixture", "password": "fixture",
    })
    packets = {"tool.example": {"source_digest": "fixture"}}
    example_index = {"examples": {}, "entries": {}}
    monkeypatch.setattr(examples, 'load_example_index', lambda path: example_index)
    monkeypatch.setattr(publisher, "load_packets", lambda *args, **kwargs: packets)
    private_config = curation_provider.DeepSeekConfig("test-only-key", max_output_tokens=configured, timeout_seconds=10)
    monkeypatch.setattr(curation_provider, "load_deepseek_config", lambda _: private_config)
    captured = {}

    class Store:
        def ensure_schema(self):
            captured["writer_initialized"] = True

    store = Store()
    monkeypatch.setattr(curation_store, "resolve_knowledge_store", lambda *, readonly: store if not readonly else None)

    def generate(config, *, allow_paid_requests=False):
        assert allow_paid_requests is True
        captured["config"] = config
        return "generator-fixture"

    def curate(passed_packets, passed_store, generator, **kwargs):
        assert passed_packets is packets and passed_store is store
        assert generator == "generator-fixture"
        captured["arguments"] = kwargs
        return {"ok": True}

    monkeypatch.setattr(curation_provider, "DeepSeekGenerator", generate)
    monkeypatch.setattr(publisher, "curate_packets", curate)
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_URL", "fixture-before")
    assert runtime.curate(limit=2, workers=1, keys="tool.example,tool.example", execute=True) == {"ok": True}
    assert captured["writer_initialized"]
    assert captured["config"].max_output_tokens == expected
    assert captured["config"].timeout_seconds == 120
    assert private_config.max_output_tokens == configured and private_config.timeout_seconds == 10
    assert captured["arguments"] == {"model": private_config.model, "limit": 2, "workers": 1,
                                     "keys": ("tool.example",),
                                     "examples_index": example_index,
                                     "source_roots": {name: Path('/opt/src') / name
                                                      for name in ('nsgablack', 'blackbase', 'mlblack')}}
