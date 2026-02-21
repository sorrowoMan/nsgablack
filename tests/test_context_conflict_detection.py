from nsgablack.utils.context.context_contracts import (
    ContextContract,
    detect_context_conflicts,
)


def test_detect_context_conflicts_reports_multi_writer_key():
    contracts = [
        ("plugin.a", ContextContract(provides=("metrics",))),
        ("plugin.b", ContextContract(mutates=("metrics",))),
    ]
    issues = detect_context_conflicts(contracts)
    assert issues
    assert any("metrics:" in x for x in issues)


def test_detect_context_conflicts_ignores_single_writer_key():
    contracts = [
        ("plugin.a", ContextContract(provides=("metrics",))),
        ("plugin.b", ContextContract(requires=("metrics",))),
    ]
    issues = detect_context_conflicts(contracts)
    assert issues == []
