from __future__ import annotations


def test_cli_catalog_search_smoke(capsys):
    from nsgablack.__main__ import main

    code = main(["catalog", "search", "vns"])
    assert code == 0
    out = capsys.readouterr().out
    assert "adapter.vns" in out


def test_cli_catalog_add_upsert(tmp_path, capsys):
    from nsgablack.__main__ import main

    target = tmp_path / "entries.toml"
    code = main(
        [
            "catalog",
            "add",
            "--file",
            str(target),
            "--key",
            "bias.demo_cli",
            "--title",
            "DemoCliBias",
            "--kind",
            "bias",
            "--import-path",
            "nsgablack.bias.domain.constraint:ConstraintBias",
            "--summary",
            "Domain bias: demo from CLI",
            "--tags",
            "bias,demo",
            "--context-requires",
            "population,generation",
            "--context-provides",
            "bias_score",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "catalog entry upserted: bias.demo_cli" in out
    text = target.read_text(encoding="utf-8")
    assert "key = 'bias.demo_cli'" in text
    assert "use_when = [" in text
    assert "minimal_wiring = [" in text
    assert "example_entry = " in text
    assert "context_requires = ['population', 'generation']" in text
    assert "context_provides = ['bias_score']" in text
