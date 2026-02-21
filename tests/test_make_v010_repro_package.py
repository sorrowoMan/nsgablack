from __future__ import annotations

from pathlib import Path

from tools.release.make_v010_repro_package import build_package


def test_build_repro_package_smoke(tmp_path: Path):
    report = build_package(tag="v0.10.0-test", output_dir=tmp_path, include_runs=False)
    package_dir = Path(report["package_dir"])
    archive = Path(report["archive"])
    manifest = Path(report["manifest"])

    assert package_dir.is_dir()
    assert archive.is_file()
    assert manifest.is_file()
    assert "README.md" in set(report["files"])
