from types import SimpleNamespace

from nsgablack.utils.viz.ui.doctor_view import (
    build_doctor_visual_hints,
    count_doctor_guard_issues,
)


def test_count_doctor_guard_issues_counts_both_guard_codes():
    report = SimpleNamespace(
        diagnostics=[
            SimpleNamespace(code="solver-mirror-write"),
            SimpleNamespace(code="solver-mirror-write"),
            SimpleNamespace(code="plugin-direct-solver-state-access"),
            SimpleNamespace(code="other"),
        ]
    )
    mirror, plugin_state = count_doctor_guard_issues(report)
    assert mirror == 2
    assert plugin_state == 1


def test_count_doctor_guard_issues_handles_missing_diagnostics():
    report = SimpleNamespace()
    mirror, plugin_state = count_doctor_guard_issues(report)
    assert mirror == 0
    assert plugin_state == 0


def test_build_doctor_visual_hints_maps_new_rule_codes():
    report = SimpleNamespace(
        diagnostics=[
            SimpleNamespace(level="warn", code="contract-key-unknown", message="bad field"),
            SimpleNamespace(level="warn", code="contract-impl-mismatch", message="read/write mismatch"),
            SimpleNamespace(level="warn", code="context-large-object-write", message="population"),
            SimpleNamespace(level="error", code="snapshot-ref-consistency", message="ref mismatch"),
            SimpleNamespace(level="warn", code="snapshot-payload-integrity", message="shape mismatch"),
        ]
    )
    hints = build_doctor_visual_hints(report, strict=False)
    by_code = {h.code: h for h in hints}
    assert by_code["contract-key-unknown"].category == "Contract"
    assert by_code["contract-impl-mismatch"].category == "Contract"
    assert by_code["context-large-object-write"].category == "Snapshot"
    assert by_code["snapshot-ref-consistency"].level == "error"
    assert by_code["snapshot-payload-integrity"].category == "Snapshot"


def test_build_doctor_visual_hints_aggregates_and_escalates_warn_in_strict():
    report = SimpleNamespace(
        diagnostics=[
            SimpleNamespace(level="warn", code="contract-key-unknown", message="x"),
            SimpleNamespace(level="warn", code="contract-key-unknown", message="y"),
        ]
    )
    hints = build_doctor_visual_hints(report, strict=True)
    assert len(hints) == 1
    hint = hints[0]
    assert hint.code == "contract-key-unknown"
    assert hint.count == 2
    assert hint.level == "error"
