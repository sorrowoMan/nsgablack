from __future__ import annotations

from nsgablack.catalog.source_sync import (
    apply_symbol_contract,
    expand_marked_component_template,
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


def test_expand_marked_bias_template_in_scaffold_project(tmp_path):
    root = tmp_path / "demo_project"
    for d in ("problem", "pipeline", "bias", "adapter", "plugins"):
        (root / d).mkdir(parents=True)
    (root / "project_registry.py").write_text("def get_project_entries():\n    return []\n", encoding="utf-8")
    (root / "build_solver.py").write_text("def build_solver():\n    return None\n", encoding="utf-8")
    (root / ".nsgablack-project").write_text("marker = nsgablack-scaffold-project\n", encoding="utf-8")
    source = root / "bias" / "demo_bias.py"
    source.write_text(
        "\n".join(
            [
                "from nsgablack.catalog.markers import component",
                "",
                '@component(kind="bias")',
                "class NewBias:",
                "    pass",
                "",
            ]
        ),
        encoding="utf-8",
    )

    final_name = expand_marked_component_template(source, "NewBias")
    assert final_name == "Bias1"

    text = source.read_text(encoding="utf-8")
    assert "class Bias1(BiasBase):" in text
    assert "def compute(self, x, context: OptimizationContext) -> float:" in text


def test_expand_template_rejects_outside_project_or_framework(tmp_path):
    source = tmp_path / "demo_bias.py"
    source.write_text(
        "\n".join(
            [
                "from nsgablack.catalog.markers import component",
                "",
                '@component(kind="bias")',
                "class NewBias:",
                "    pass",
                "",
            ]
        ),
        encoding="utf-8",
    )

    try:
        expand_marked_component_template(source, "NewBias")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "only enabled inside NSGABlack framework or scaffold projects" in str(exc)
