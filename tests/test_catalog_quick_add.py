from pathlib import Path

from nsgablack.catalog.quick_add import build_entry_payload, upsert_catalog_entry


def test_build_entry_payload_fills_explicit_usage_fields():
    payload = build_entry_payload(
        key="bias.demo_soft",
        title="DemoSoftBias",
        kind="bias",
        import_path="nsgablack.bias.domain.constraint:ConstraintBias",
        summary="demo",
        tags=("bias", "demo"),
    )
    assert payload["use_when"]
    assert payload["minimal_wiring"]
    assert payload["required_companions"]
    assert payload["config_keys"]
    assert str(payload["example_entry"]).strip()


def test_upsert_catalog_entry_replaces_same_key(tmp_path):
    target = tmp_path / "entries.toml"
    target.write_text(
        "[[entry]]\n"
        "key = 'bias.demo_soft'\n"
        "title = 'OldTitle'\n"
        "kind = 'bias'\n"
        "import_path = 'nsgablack.bias.domain.constraint:ConstraintBias'\n"
        "tags = ['bias']\n"
        "summary = 'old'\n"
        "companions = []\n"
        "use_when = ['old']\n"
        "minimal_wiring = ['old']\n"
        "required_companions = ['(none)']\n"
        "config_keys = ['(none)']\n"
        "example_entry = 'old'\n",
        encoding="utf-8",
    )

    payload = build_entry_payload(
        key="bias.demo_soft",
        title="NewTitle",
        kind="bias",
        import_path="nsgablack.bias.domain.constraint:ConstraintBias",
        summary="new",
        tags=("bias", "demo"),
    )
    upsert_catalog_entry(Path(target), payload, replace=True)
    text = target.read_text(encoding="utf-8")
    assert text.count("[[entry]]") == 1
    assert "NewTitle" in text
    assert "OldTitle" not in text


def test_upsert_writes_context_contract_fields(tmp_path):
    target = tmp_path / "entries.toml"
    payload = build_entry_payload(
        key="adapter.demo_context",
        title="DemoAdapter",
        kind="adapter",
        import_path="nsgablack.adapters.vns:VNSAdapter",
        summary="adapter demo",
        context_requires=("population_ref", "generation"),
        context_provides=("vns_k",),
        context_mutates=("population_ref",),
        context_cache=("objectives_ref",),
        context_notes=("writes vns diagnostics",),
    )
    upsert_catalog_entry(target, payload, replace=True)
    text = target.read_text(encoding="utf-8")
    assert "context_requires = ['population_ref', 'generation']" in text
    assert "context_provides = ['vns_k']" in text
    assert "context_mutates = ['population_ref']" in text
    assert "context_cache = ['objectives_ref']" in text
    assert "context_notes = ['writes vns diagnostics']" in text
