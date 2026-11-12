"""显式 opt-in 的全 registry 故障矩阵；约需五分钟，不计入 benchmark 时间。

PowerShell：
    $env:NSGABLACK_FULL_TRANSPARENCY_FAULTS = "1"
    .benchmark-venv/Scripts/python.exe -m pytest tests/test_transparency_fault_matrix.py -q

所有 SQLite grant、文件 Snapshot、checkpoint 和汇总都写入工作区 .test-tmp，
不依赖操作系统临时目录。未设置环境变量时不会运行任何故障 Case。
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from benchmarks import transparency_registry as registry
from benchmarks.transparency_faults import run_fault_checks


SPECS = registry.specs()
WORKSPACE = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.environ.get("NSGABLACK_FULL_TRANSPARENCY_FAULTS") != "1",
    reason="expensive complete fault matrix; set NSGABLACK_FULL_TRANSPARENCY_FAULTS=1 to opt in")


@pytest.fixture(scope="session")
def workspace_fault_matrix():
    directory = WORKSPACE / ".test-tmp" / "transparency_full_fault_matrix" / uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    results = []
    sources = ("adapters/unit_backed.py", "adapters/mas/adapter.py",
               "adapters/async_event_driven/adapter.py", "benchmarks/transparency_faults.py",
               "benchmarks/transparency_registry.py", "benchmarks/transparency_protocols.py")
    hashes = {name: sha256((WORKSPACE / name).read_bytes()).hexdigest() for name in sources}
    try:
        yield directory, results
    finally:
        summary = {"schema": "nsgablack.transparency_fault_matrix/v1", "seed": 11,
            "expected_specs": [spec.name for spec in SPECS], "source_sha256": hashes,
            "complete": len(results) == len(SPECS),
            "summary": {"expected": len(SPECS), "executed": len(results),
                "passed": sum(row["status"] == "passed" for row in results),
                "failed": sum(row["status"] != "passed" for row in results)},
            "results": results, "scope": "Project L0 unit resource fixture; excluded from paired benchmark timing"}
        (directory / "matrix_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.name)
def test_registry_fault_matrix(spec, workspace_fault_matrix):
    directory, results = workspace_fault_matrix
    report = run_fault_checks(spec, seed=11, work_dir=directory)
    results.append(report)
    (directory / (spec.name + ".json")).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    assert report["status"] == "passed", report
    assert {row["mode"] for row in report["modes"]} == {"runtime_error", "cancellation"}
    assert all(all(row["checks"].values()) for row in report["modes"])
