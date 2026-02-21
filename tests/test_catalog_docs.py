from __future__ import annotations


def test_catalog_has_doc_entries():
    from nsgablack.catalog import get_catalog

    c = get_catalog(refresh=True)
    docs = c.list(kind="doc")
    assert docs
    assert any(e.key == "doc.user_guide.catalog" for e in docs)


def test_cli_catalog_list_doc_kind(capsys):
    from nsgablack.__main__ import main

    code = main(["catalog", "list", "--kind", "doc", "--no-summary"])
    assert code == 0
    out = capsys.readouterr().out
    assert "doc.user_guide.catalog" in out
    assert "Doc" in out


def test_cli_catalog_list_multi_kind(capsys):
    from nsgablack.__main__ import main

    code = main(["catalog", "list", "--kind", "adapter", "--kind", "doc", "--no-summary"])
    assert code == 0
    out = capsys.readouterr().out
    assert "adapter.vns" in out
    assert "doc.user_guide.catalog" in out

