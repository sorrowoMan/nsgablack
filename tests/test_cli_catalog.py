from __future__ import annotations


def test_cli_catalog_search_smoke(capsys):
    from nsgablack.__main__ import main

    code = main(["catalog", "search", "vns"])
    assert code == 0
    out = capsys.readouterr().out
    assert "adapter.vns" in out

