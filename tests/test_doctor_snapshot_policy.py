from __future__ import annotations

from nsgablack.project import run_project_doctor


def _write_build_solver(path, serializer: str) -> None:
    (path / ".case").write_text("kind = solver\n", encoding="utf-8")
    (path / "build_solver.py").write_text(
        "class DummySolver:\n"
        "    snapshot_store_backend = 'redis'\n"
        "    snapshot_store_key_prefix = 'demo:project:snapshot'\n"
        f"    snapshot_store_serializer = {serializer!r}\n"
        "    snapshot_store_ttl_seconds = 60\n"
        "    context_store_backend = 'memory'\n"
        "\n"
        "def build_solver(*, resource_context=None, component_overrides=None):\n"
        "    del resource_context, component_overrides\n"
        "    return DummySolver()\n",
        encoding="utf-8",
    )


def test_doctor_warns_when_snapshot_redis_uses_pickle_unsafe(tmp_path):
    _write_build_solver(tmp_path, "pickle_unsafe")
    report = run_project_doctor(tmp_path, instantiate_solver=True, strict=False)
    rows = [d for d in report.diagnostics if d.code == "snapshot-redis-pickle-unsafe"]
    assert rows
    assert all(d.level == "warn" for d in rows)


def test_doctor_strict_escalates_snapshot_redis_pickle_unsafe(tmp_path):
    _write_build_solver(tmp_path, "pickle_unsafe")
    report = run_project_doctor(tmp_path, instantiate_solver=True, strict=True)
    rows = [d for d in report.diagnostics if d.code == "snapshot-redis-pickle-unsafe"]
    assert rows
    assert all(d.level == "error" for d in rows)


def _write_context_build_solver(
    path,
    serializer: str,
    *,
    allow_legacy: bool = False,
) -> None:
    (path / ".case").write_text("kind = solver\n", encoding="utf-8")
    (path / "build_solver.py").write_text(
        "class DummySolver:\n"
        "    context_store_backend = 'redis'\n"
        "    context_store_key_prefix = 'demo:project:context'\n"
        f"    context_store_serializer = {serializer!r}\n"
        f"    context_store_unsafe_allow_legacy_pickle = {allow_legacy!r}\n"
        "    context_store_max_payload_bytes = 262144\n"
        "    context_store_ttl_seconds = 60\n"
        "    snapshot_store_backend = 'memory'\n"
        "\n"
        "def build_solver(*, resource_context=None, component_overrides=None):\n"
        "    del resource_context, component_overrides\n"
        "    return DummySolver()\n",
        encoding="utf-8",
    )


def test_doctor_strict_rejects_unsafe_redis_context_pickle(tmp_path):
    _write_context_build_solver(tmp_path, "pickle_unsafe")

    report = run_project_doctor(tmp_path, instantiate_solver=True, strict=True)

    rows = [d for d in report.diagnostics if d.code == "redis-context-pickle-unsafe"]
    assert rows and all(d.level == "error" for d in rows)


def test_doctor_strict_rejects_legacy_context_pickle_migration_mode(tmp_path):
    _write_context_build_solver(tmp_path, "pickle_signed", allow_legacy=True)

    report = run_project_doctor(tmp_path, instantiate_solver=True, strict=True)

    rows = [
        d
        for d in report.diagnostics
        if d.code == "redis-context-legacy-pickle-enabled"
    ]
    assert rows and all(d.level == "error" for d in rows)

