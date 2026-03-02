from __future__ import annotations

from nsgablack.project import run_project_doctor


def _write_build_solver(path, serializer: str) -> None:
    (path / "build_solver.py").write_text(
        "class DummySolver:\n"
        "    snapshot_store_backend = 'redis'\n"
        "    snapshot_store_key_prefix = 'demo:project:snapshot'\n"
        f"    snapshot_store_serializer = {serializer!r}\n"
        "    snapshot_store_ttl_seconds = 60\n"
        "    context_store_backend = 'memory'\n"
        "\n"
        "def build_solver(argv=None):\n"
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

