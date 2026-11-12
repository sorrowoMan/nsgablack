"""Create an explicit source-only Docker context; never read credentials or Git blobs.

Run from any directory. Uncommitted and untracked source is intentionally included.
Every included file is hashed. Secrets/config/data/caches are denied before reading.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tomllib


REPO = Path(__file__).resolve().parents[2]
SOURCE_DIRS = ("nsgablack", "adapters", "bias", "catalog", "core", "experiment",
               "plugins", "project", "representation", "units", "ui", "utils", "docs", "examples")
ML_SOURCE_DIRS = ("assembly", "backends", "bias", "capabilities", "catalog", "core",
                  "integrations", "models", "pipeline", "presets", "problems", "project",
                  "representations", "docs", "examples")
ROOT_FILES = ("pyproject.toml", "README.md", "LICENSE", "MANIFEST.in", "__init__.py", "__main__.py")
ML_ROOT_FILES = ROOT_FILES + ("cli.py", "context_keys.py")
EXTENSIONS = {".py", ".pyi", ".toml", ".json", ".md", ".rst", ".txt", ".yaml", ".yml",
              ".ini", ".cfg", ".template", ".html", ".css", ".js", ".svg"}
SPECIAL_FILES = {".case", ".gitkeep"}
DENIED_DIRS = {".git", ".github", ".venv", "venv", "env", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".blackbase", "checkpoints",
    "results", "runs", "outputs", "data", "datasets", "artifacts", "build", "dist", "htmlcov",
    "test-results", "playwright-report", "attachments", "_archive", "_build", "reports",
    "evidence", "private", "secrets", "notes", "qas", "tests", ".eggs"}
GENERATED_METADATA_SUFFIXES = (".egg-info", ".dist-info")
SECRET_EXTENSIONS = {".pem", ".key", ".p12", ".pfx", ".ppk", ".der", ".crt", ".cer", ".gpg", ".keystore"}
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
SECRET_MARKERS = (
    re.compile(rb"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    re.compile(rb"\b(?:AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{20,})\b"),
    re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}\b"),
)


def linked(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


def denied_directory(name: str) -> bool:
    value = name.lower()
    return value in DENIED_DIRS or value.endswith(GENERATED_METADATA_SUFFIXES)


def allowed(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(denied_directory(part) for part in relative.parts[:-1]):
        return False
    name = path.name.lower()
    if (name.startswith(".env") or name.startswith("db.toml")
            or name.endswith(GENERATED_METADATA_SUFFIXES)
            or name in {"id_rsa", "id_ed25519", "authorized_keys", "known_hosts"}
            or any(token in name for token in ("credentials", "private_key", ".secret", ".local."))
            or path.suffix.lower() in SECRET_EXTENSIONS):
        return False
    if relative.parts[:2] == ("docs", "development") and name not in {
            "component_api_index_full_cn.md", "component_api_index_framework_core_cn.md"}:
        return False
    return path.suffix.lower() in EXTENSIONS or name in SPECIAL_FILES


def collect_tree(directory: Path, root: Path):
    if not directory.exists() or linked(directory):
        return
    for current, dirs, files in os.walk(directory, followlinks=False):
        base = Path(current)
        dirs[:] = sorted(name for name in dirs if not denied_directory(name)
                         and not linked(base / name))
        for name in sorted(files):
            path = base / name
            if linked(path) or not allowed(path, root):
                continue
            path.resolve().relative_to(root.resolve())
            yield path


def revision(root: Path):
    def git(*arguments):
        result = subprocess.run(["git", "-C", str(root), *arguments],
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        return result.stdout.strip() if result.returncode == 0 else None
    head = git("rev-parse", "HEAD")
    status = git("status", "--porcelain", "--untracked-files=all")
    return {"head": head, "dirty": None if status is None else bool(status),
            "changed_paths_count": None if status is None else len(status.splitlines()),
            "selection": "current filesystem whitelist, including uncommitted/untracked source; not git archive"}


def build_context(nsgablack: Path, blackbase: Path, output: Path, *, mlblack: Path | None = None,
                  project_assets: tuple[str, ...] = ()):
    nsgablack, blackbase = nsgablack.resolve(), blackbase.resolve()
    mlblack = (mlblack or nsgablack.parent / "mlblack").resolve()
    payload = {}

    def add(path: Path, archive_path: str):
        if linked(path):
            raise ValueError("Cannot package a symlink or junction")
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError(f"Source file exceeds explicit 2 MiB limit: {archive_path}")
        data = path.read_bytes()
        if any(pattern.search(data) for pattern in SECRET_MARKERS):
            raise ValueError(f"Credential-shaped content rejected without printing its value: {archive_path}")
        if archive_path in payload:
            raise ValueError("Duplicate archive path: " + archive_path)
        payload[archive_path] = data

    for name in ROOT_FILES:
        path = nsgablack / name
        if path.is_file():
            add(path, "nsgablack/" + name)
    for name in SOURCE_DIRS:
        for path in collect_tree(nsgablack / name, nsgablack):
            add(path, "nsgablack/" + path.relative_to(nsgablack).as_posix())
    for name in ("pyproject.toml", "README.md"):
        add(blackbase / name, "blackbase/" + name)
    for path in collect_tree(blackbase / "src", blackbase):
        add(path, "blackbase/" + path.relative_to(blackbase).as_posix())
    for name in ML_ROOT_FILES:
        path = mlblack / name
        if path.is_file():
            add(path, "mlblack/" + name)
    for name in ML_SOURCE_DIRS:
        for path in collect_tree(mlblack / name, mlblack):
            add(path, "mlblack/" + path.relative_to(mlblack).as_posix())
    # Business data is never collected by the general source walk. A deployment
    # operator may explicitly include small assets of a trusted formal Case.
    selected_assets = []
    for relative in project_assets:
        member = PurePosixPath(relative.replace("\\", "/"))
        if (member.is_absolute() or ".." in member.parts or len(member.parts) < 6
                or member.parts[:2] != ("examples", "cases") or member.parts[3] != "cases"
                or member.suffix.lower() not in {".csv", ".xlsx"}
                or any(part.lower() in {"secrets", "private", "runs", ".git"} for part in member.parts)
                or any(word in member.name.lower() for word in ("credential", "secret", "password"))):
            raise ValueError("Project asset must be an explicit CSV/XLSX in a formal Case")
        asset = nsgablack.joinpath(*member.parts)
        asset.resolve().relative_to(nsgablack)
        if any(linked(nsgablack.joinpath(*member.parts[:i])) for i in range(1, len(member.parts) + 1)):
            raise ValueError("Project asset cannot traverse a link")
        case = nsgablack.joinpath(*member.parts[:5])
        project = nsgablack.joinpath(*member.parts[:3])
        required_entries = (project / "project_config.py", project / "run_project.py",
                            project / "cases" / "__init__.py", case / "__init__.py", case / "build_solver.py")
        if any(not path.is_file() or linked(path) for path in required_entries):
            raise ValueError("Project asset has no formal Project/Case entry")
        archive_path = "nsgablack/" + member.as_posix()
        if archive_path not in payload:
            add(asset, archive_path)
        selected_assets.append(member.as_posix())
    deploy = nsgablack / "deployment/catalog"
    for name in ("Dockerfile", "requirements-web.txt", "README.md", "package_context.py", "verify_release.py", "verify_ui.py", "verify_knowledge.py", "verify_search_filters.py", "verify_examples.py", "verify_navigation.py", "verify_lab.py", "verify_lab_ai.py", "build_examples.py", "run_example_receipts.py", "runtime.py", "auto_curate.py", "complete_catalog.py", "completion_worker.py", "gateway.conf", "verify_gateway.py"):
        add(deploy / name, name)

    required = {"nsgablack/catalog/entries/core_architecture.toml", "nsgablack/catalog/guidance.py",
        "nsgablack/docs/architecture/CATALOG_USAGE_CN.md", "nsgablack/catalog/dashboard.py",
        "nsgablack/catalog/dashboard_shell.py", "blackbase/src/blackbase/catalog.py",
        "mlblack/pyproject.toml", "mlblack/__init__.py", "mlblack/catalog/registry.py",
        "mlblack/catalog/entries/codec.toml"}
    if not required <= set(payload):
        raise ValueError("Deployment source closure is incomplete: " + str(sorted(required - set(payload))))
    size = sum(map(len, payload.values()))
    if size > MAX_TOTAL_BYTES:
        raise ValueError("Explicit source context exceeds 64 MiB; review the whitelist")
    def image_path(name):
        return "/opt/src/" + name if name.startswith(("nsgablack/", "blackbase/", "mlblack/")) else "/opt/catalog/" + name

    files = [{"path": name, "image_path": image_path(name), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
             for name, data in sorted(payload.items())]
    content_sha256 = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    manifest = {"schema": "nsgablack.catalog_deployment_context/v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "content_sha256": content_sha256,
        "source_file_count": len(files), "source_bytes": size,
        "roots": {"nsgablack": revision(nsgablack), "blackbase": revision(blackbase), "mlblack": revision(mlblack)},
        "versions": {name: tomllib.loads(payload[name + "/pyproject.toml"].decode("utf-8-sig"))["project"]["version"]
                     for name in ("nsgablack", "blackbase", "mlblack")},
        "policy": {"source_directories": list(SOURCE_DIRS), "ml_source_directories": list(ML_SOURCE_DIRS),
                   "explicit_project_assets": sorted(set(selected_assets)),
                   "excluded_directories": sorted(DENIED_DIRS),
                   "excluded_directory_suffixes": list(GENERATED_METADATA_SUFFIXES),
                   "private_config": "all .env*, db.toml*, key/certificate files denied before reading",
                   "max_file_bytes": MAX_FILE_BYTES, "max_context_bytes": MAX_TOTAL_BYTES,
                   "source_revision_note": "HEAD alone does not identify this dirty deployment; file hashes do."},
        "files": files}
    manifest_data = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    # The manifest itself is not recursively hashed in its own file list.
    payload["release-manifest.json"] = manifest_data
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = output / f"catalog-context-{stamp}-{content_sha256[:12]}.tar.gz"
    with destination.open("wb") as stream, gzip.GzipFile(filename="", fileobj=stream, mode="wb", mtime=0) as compressed:
        with tarfile.open(mode="w", fileobj=compressed) as archive:
            for name, data in sorted(payload.items()):
                safe_name = PurePosixPath(name)
                if safe_name.is_absolute() or ".." in safe_name.parts:
                    raise ValueError("Unsafe archive member")
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = len(data), 0o644, 0
                info.uid = info.gid = 0
                archive.addfile(info, io.BytesIO(data))
    sidecar = destination.with_suffix("").with_suffix(".manifest.json")
    sidecar.write_bytes(manifest_data)
    archive_sha = hashlib.sha256(destination.read_bytes()).hexdigest()
    print(json.dumps({"archive": str(destination), "manifest": str(sidecar), "archive_sha256": archive_sha,
        "archive_bytes": destination.stat().st_size, "members": len(payload),
        "source_files": len(files), "source_bytes": size, "content_sha256": content_sha256}, ensure_ascii=False))
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nsgablack", type=Path, default=REPO)
    parser.add_argument("--blackbase", type=Path, default=REPO.parent / "blackbase")
    parser.add_argument("--mlblack", type=Path, default=REPO.parent / "mlblack")
    parser.add_argument("--output", type=Path, default=REPO / ".pytest_cache/catalog-deploy")
    parser.add_argument("--project-asset", action="append", default=[],
                        help="Explicit relative CSV/XLSX under a formal Case; not a data directory glob")
    args = parser.parse_args()
    build_context(args.nsgablack, args.blackbase, args.output, mlblack=args.mlblack,
                  project_assets=tuple(args.project_asset))


if __name__ == "__main__":
    main()
