from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Iterable, List


DEFAULT_FILES: tuple[str, ...] = (
    "README.md",
    "START_HERE.md",
    "QUICKSTART.md",
    "WORKFLOW_END_TO_END.md",
    "docs/evidence/ONE_PAGE_COMPARISON.md",
    "docs/evidence/MIN_REPRO_10MIN.md",
    "docs/evidence/BASELINE_PROTOCOL.md",
    "docs/user_guide/RUN_INSPECTOR.md",
    "docs/user_guide/CONTEXT_FIELD_RULES.md",
    "docs/changelog/RUN_INSPECTOR_CHANGELOG.md",
    "benchmarks/fixed_baseline_runner.py",
    "tools/context_field_guard.py",
    "tools/schema_tool.py",
)


def _ensure_repo_parent_on_sys_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    repo_parent = repo_root.parent
    if str(repo_parent) not in sys.path:
        sys.path.insert(0, str(repo_parent))
    return repo_root


def _copy_paths(repo_root: Path, package_root: Path, rel_paths: Iterable[str]) -> List[str]:
    copied: List[str] = []
    for rel in rel_paths:
        rel_clean = str(rel).strip().replace("\\", "/")
        if not rel_clean:
            continue
        src = (repo_root / rel_clean).resolve()
        if not src.exists():
            continue
        dst = package_root / rel_clean
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        copied.append(rel_clean)
    return copied


def _find_latest_file(base_dir: Path, pattern: str) -> Path | None:
    if not base_dir.is_dir():
        return None
    candidates = sorted(
        base_dir.glob(pattern),
        key=lambda p: (p.stat().st_mtime, p.name),
        reverse=True,
    )
    return candidates[0] if candidates else None


def _write_manifest(
    package_root: Path,
    *,
    tag: str,
    copied_files: List[str],
    baseline_summary: str | None,
    baseline_raw: str | None,
) -> Path:
    from nsgablack.utils.engineering.schema_version import stamp_schema

    payload = {
        "tag": str(tag),
        "generated_at": time.strftime("%Y%m%d_%H%M%S"),
        "files": copied_files,
        "artifacts": {
            "baseline_summary": baseline_summary,
            "baseline_raw": baseline_raw,
        },
    }
    payload = stamp_schema(payload, "benchmark_summary")
    manifest = package_root / "manifest.json"
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def build_package(
    *,
    tag: str = "v0.10.0",
    output_dir: Path = Path("runs/release"),
    include_runs: bool = True,
) -> dict:
    repo_root = _ensure_repo_parent_on_sys_path()
    ts = time.strftime("%Y%m%d_%H%M%S")
    package_name = f"nsgablack_repro_{str(tag).replace('/', '_')}_{ts}"
    package_root = output_dir.resolve() / package_name
    package_root.mkdir(parents=True, exist_ok=True)

    copied_files = _copy_paths(repo_root, package_root, DEFAULT_FILES)

    baseline_summary_rel = None
    baseline_raw_rel = None
    if include_runs:
        runs_dir = repo_root / "runs" / "evidence" / "baseline"
        summary = _find_latest_file(runs_dir, "baseline_summary_*.json")
        raw = _find_latest_file(runs_dir, "baseline_raw_*.csv")
        extra_paths: List[str] = []
        if summary is not None:
            extra_paths.append(str(summary.relative_to(repo_root)))
            baseline_summary_rel = str(summary.relative_to(repo_root)).replace("\\", "/")
        if raw is not None:
            extra_paths.append(str(raw.relative_to(repo_root)))
            baseline_raw_rel = str(raw.relative_to(repo_root)).replace("\\", "/")
        copied_files.extend(_copy_paths(repo_root, package_root, extra_paths))

    manifest = _write_manifest(
        package_root,
        tag=tag,
        copied_files=sorted(set(copied_files)),
        baseline_summary=baseline_summary_rel,
        baseline_raw=baseline_raw_rel,
    )

    archive_path = shutil.make_archive(
        base_name=str(package_root),
        format="zip",
        root_dir=str(package_root),
    )
    return {
        "package_dir": str(package_root),
        "archive": str(Path(archive_path)),
        "manifest": str(manifest),
        "files": sorted(set(copied_files)),
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build reproducible release package for NSGABlack.")
    parser.add_argument("--tag", default="v0.10.0", help="Release tag marker in package metadata.")
    parser.add_argument("--output-dir", default="runs/release", help="Output directory for package.")
    parser.add_argument(
        "--no-runs",
        action="store_true",
        help="Skip copying latest baseline run artifacts.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = build_package(
        tag=str(args.tag),
        output_dir=Path(str(args.output_dir)),
        include_runs=not bool(args.no_runs),
    )
    print(f"package_dir={report['package_dir']}")
    print(f"archive={report['archive']}")
    print(f"manifest={report['manifest']}")
    print(f"files={len(report['files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
