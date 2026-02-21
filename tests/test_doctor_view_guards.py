from types import SimpleNamespace

from nsgablack.utils.viz.ui.doctor_view import count_doctor_guard_issues


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
