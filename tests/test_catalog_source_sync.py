from __future__ import annotations

from nsgablack.catalog.source_sync import (
    apply_symbol_contract,
    list_source_symbols,
    read_symbol_contract,
)


def test_source_sync_scan_read_and_apply(tmp_path):
    source = tmp_path / "demo_component.py"
    source.write_text(
        "\n".join(
            [
                "class DemoBias:",
                '    \"\"\"demo bias\"\"\"',
                "    context_requires = ('population',)",
                "    context_provides = ()",
                "    def compute(self, x, context):",
                "        return 0.0",
                "",
                "class DemoPlugin:",
                "    pass",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    symbols = list_source_symbols(source)
    by_name = {s.name: s for s in symbols}
    assert by_name["DemoBias"].kind == "bias"
    assert by_name["DemoPlugin"].kind == "plugin"

    contract = read_symbol_contract(source, "DemoBias")
    assert contract["context_requires"] == ("population",)
    assert contract["context_provides"] == ()
    assert contract["context_mutates"] == ()

    apply_symbol_contract(
        source,
        "DemoBias",
        {
            "context_requires": ("generation",),
            "context_provides": ("bias_score",),
            "context_mutates": ("population",),
            "context_cache": ("objectives",),
            "context_notes": ("tracks score history",),
        },
    )
    updated = read_symbol_contract(source, "DemoBias")
    assert updated["context_requires"] == ("generation",)
    assert updated["context_provides"] == ("bias_score",)
    assert updated["context_mutates"] == ("population",)
    assert updated["context_cache"] == ("objectives",)
    assert updated["context_notes"] == ("tracks score history",)

