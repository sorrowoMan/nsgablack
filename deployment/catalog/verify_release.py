#!/usr/bin/env python3
"""Read-only Catalog release acceptance, without starting Streamlit or a solver.

Image: python /opt/catalog/verify_release.py --require-hosted
Local context: python deployment/catalog/verify_release.py --manifest PATH \
    --context-root PATH
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, redirect_stdout
import hashlib
import importlib
from importlib import metadata
import io
import json
from pathlib import Path, PurePosixPath
import re
from unittest.mock import patch


class VerificationError(RuntimeError):
    pass


SCENARIOS = (
    ("贝叶斯引导", "adapter.bayesian_optimization", "adapter"),
    ("替换采集函数", "tool.bo_acquisition", "acquisition"),
    ("种群扩展字段", "tool.population_change", "member_change"),
    ("GA停滞VNS精修", "adapter.search_plan", "orchestration"),
)


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(manifest_path, context_root):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest.get("schema") == "nsgablack.catalog_deployment_context/v1", "unexpected release manifest schema")
    files = manifest.get("files")
    require(isinstance(files, list) and bool(files), "release manifest has no file whitelist")
    indexed, total_bytes = {}, 0
    for item in files:
        require(isinstance(item, dict), "invalid manifest file record")
        name = item.get("path")
        require(isinstance(name, str) and bool(name) and "\\" not in name, "invalid whitelist file path")
        relative = PurePosixPath(name)
        require(not relative.is_absolute() and ".." not in relative.parts and name not in indexed,
                "unsafe or duplicate whitelist file path")
        expected = item.get("sha256")
        require(isinstance(expected, str) and bool(re.fullmatch(r"[0-9a-f]{64}", expected)), "invalid whitelist SHA256")
        size = item.get("bytes")
        require(type(size) is int and size >= 0, "invalid whitelist file size")
        if context_root is not None:
            path = context_root.joinpath(*relative.parts).resolve()
            require(path.is_relative_to(context_root), "whitelist file escapes the local context")
        else:
            image_name = item.get("image_path")
            require(isinstance(image_name, str), "manifest file has no image_path")
            image_path = PurePosixPath(image_name)
            allowed_roots = (PurePosixPath("/opt/src/nsgablack"), PurePosixPath("/opt/src/blackbase"), PurePosixPath("/opt/src/mlblack"), PurePosixPath("/opt/catalog"))
            require(image_path.is_absolute() and ".." not in image_path.parts
                    and any(image_path.is_relative_to(root) for root in allowed_roots), "unsafe image file path")
            path = Path(image_name).resolve()
            require(any(path.is_relative_to(Path(str(root)).resolve()) for root in allowed_roots), "image file escapes its source root")
        require(path.is_file(), f"missing release file: {name}")
        require(path.stat().st_size == size and sha256(path) == expected, f"release file hash mismatch: {name}")
        indexed[name] = {"sha256": expected, "resolved": path}
        total_bytes += size
    content_hash = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    require(manifest.get("content_sha256") == content_hash, "manifest whitelist digest mismatch")
    require(manifest.get("source_file_count") == len(indexed) and manifest.get("source_bytes") == total_bytes,
            "manifest whitelist totals mismatch")
    return manifest, indexed, {"files": len(indexed), "bytes": total_bytes, "content_sha256": content_hash}


def module_source_record(module_name, indexed):
    module = importlib.import_module(module_name)
    path = Path(module.__file__).resolve()
    require(path.suffix == ".py" and path.is_file(), f"module has no inspectable Python source: {module_name}")
    package, *parts = module_name.split(".")
    suffix = "/".join((*parts, "__init__.py")) if path.name == "__init__.py" else "/".join(parts) + ".py"
    if package == "blackbase":
        candidates = ("blackbase/src/blackbase/" + suffix,)
    elif package == "mlblack":
        candidates = ("mlblack/" + (suffix if parts else "__init__.py"),)
    elif parts:
        candidates = ("nsgablack/" + suffix,)
    else:
        candidates = ("nsgablack/nsgablack/__init__.py", "nsgablack/__init__.py")
    matching = [name for name in candidates if name in indexed and indexed[name]["sha256"] == sha256(path)]
    require(bool(matching), f"loaded module differs from the whitelisted release: {module_name}")
    require(path == indexed[matching[0]]["resolved"],
            f"loaded module is outside the verified source tree: {module_name}")
    return module, {"path": str(path), "manifest_path": matching[0], "sha256": indexed[matching[0]]["sha256"]}


def verify_release(args):
    manifest_path = args.manifest.resolve()
    context_root = None if args.context_root is None else args.context_root.resolve()
    manifest, indexed, file_summary = verify_manifest(manifest_path, context_root)
    modules, paths = {}, {}
    for name in ("nsgablack", "blackbase", "mlblack", "mlblack.catalog.registry", "blackbase.catalog", "nsgablack.catalog.registry",
                 "nsgablack.catalog.facade", "nsgablack.catalog.guidance", "nsgablack.catalog.dashboard"):
        modules[name], paths[name] = module_source_record(name, indexed)
    versions = {}
    for name in ("nsgablack", "blackbase", "mlblack"):
        module_version = str(getattr(modules[name], "__version__", ""))
        require(bool(module_version), f"package has no declared version: {name}")
        try:
            installed_version = metadata.version(name)
        except metadata.PackageNotFoundError:
            installed_version = None
        if installed_version is not None:
            require(installed_version == module_version, f"distribution and module versions differ: {name}")
        expected = manifest.get("versions", {}).get(name)
        if expected is not None:
            require(module_version == str(expected), f"release package version mismatch: {name}")
        versions[name] = {"module": module_version, "distribution": installed_version}

    from nsgablack.catalog import facade, registry
    from nsgablack.catalog.fingerprint import CATALOG_SOURCE_SCHEMA, catalog_entries_digest
    from nsgablack.catalog.guidance import guidance_for
    from nsgablack.catalog.store import mysql, postgres
    from nsgablack.units.contracts import UnitBinding

    forbidden_calls = {"database": 0, "unit_build": 0}

    def database_forbidden(*unused, **kwargs):
        forbidden_calls["database"] += 1
        raise VerificationError("source_mode=off attempted database access")

    def unit_forbidden(*unused, **kwargs):
        forbidden_calls["unit_build"] += 1
        raise VerificationError("Catalog acceptance attempted to construct an algorithm Unit")

    profiles, scenarios = {}, {}
    with ExitStack() as stack:
        stack.enter_context(patch.object(mysql, "_connect_mysql", database_forbidden))
        stack.enter_context(patch.object(postgres, "_connect_postgres", database_forbidden))
        stack.enter_context(patch.object(facade, "resolve_catalog_store", database_forbidden))
        stack.enter_context(patch.object(UnitBinding, "build", unit_forbidden))
        for profile in ("default", "framework-core"):
            entries = facade.list_entries(profile=profile, source_mode="off", limit=None)
            source = registry.get_source_catalog(profile=profile).list()
            summary = facade.catalog_summary(profile=profile, source_mode="off")
            require(summary["total"] == len(entries), f"Catalog summary count mismatch: {profile}")
            require(len({item.key for item in entries}) == len(entries), f"duplicate Catalog keys: {profile}")
            if profile == "framework-core":
                require(all(item.kind not in {"doc", "example"} and "examples/" not in item.import_path.replace(".", "/").replace("\\", "/").lower()
                            for item in entries), "framework-core exposes an example or documentation implementation")
            profiles[profile] = {"total": summary["total"], "by_kind": summary["by_kind"],
                                 "source_schema": CATALOG_SOURCE_SCHEMA, "source_digest": catalog_entries_digest(source)}
            ml_entries = [item for item in entries if item.metadata.get("catalog_framework") == "mlblack"]
            require(bool(ml_entries), f"ML catalog provider was not included: {profile}")
            profiles[profile]["mlblack_total"] = len(ml_entries)
            for original_key in ("codec.linear_point", "codec.neural_graph", "integration.learning_solver"):
                key = "mlblack." + original_key
                found = next((item for item in ml_entries if item.key == key), None)
                require(found is not None, f"ML catalog entry missing: {key}")
                require(found.metadata.get("catalog_original_key") == original_key,
                        f"ML catalog entry lost its original identity: {key}")
                payload = facade._entry_payload(found)
                require(payload["metadata"].get("catalog_framework") == "mlblack",
                        f"ML UI payload lost its source: {key}")
                hits = facade.search_entries(found.title, profile=profile, source_mode="off", limit=100)
                require(any(item.key == key for item in hits), f"ML entry cannot be found by title: {key}")
                scenarios[f"{profile}:{key}"] = {"key": key, "kind": found.kind, "source": "mlblack"}
            for query, expected_key, expected_role in SCENARIOS:
                hits = facade.search_entries(query, profile=profile, source_mode="off", limit=100)
                found = next((item for item in hits if item.key == expected_key), None)
                require(found is not None, f"Chinese scenario did not find its expected key: {query}")
                require(guidance_for(found).role == expected_role, f"scenario role mismatch: {expected_key}")
                payload = facade._entry_payload(found)
                require(isinstance(payload["operations"], (tuple, list)) and isinstance(payload["config_keys"], (tuple, list))
                        and isinstance(payload["wiring_status"], str) and isinstance(payload["wiring_notes"], (tuple, list)),
                        f"Catalog payload does not separate operations, configuration and status: {expected_key}")
                require(payload["wiring_status"] in {"guidance", "template", "signature-checked", "unverified", "invalid"},
                        f"Catalog payload overstates verification: {expected_key}")
                scenarios[f"{profile}:{query}"] = {"key": found.key, "role": payload["role"], "status": payload["wiring_status"]}
        require(not any(forbidden_calls.values()), "read-only Catalog verification crossed an execution boundary")

    dashboard = modules["nsgablack.catalog.dashboard"]
    hosted = dashboard._hosted_mode()
    if args.require_hosted:
        require(hosted, "hosted Catalog mode is not enabled")
    require(dashboard._HOSTED_SOURCE_VALUES == {"scope": "framework", "project_path": "", "include_global": False,
                                               "db_path": "", "source_mode": "off"}, "hosted Catalog source policy differs from the release contract")
    return {"ok": True, "manifest_schema": manifest["schema"], "files": file_summary,
            "versions": versions, "source_paths": paths, "profiles": profiles,
            "scenarios": scenarios, "read_only": forbidden_calls, "hosted": hosted}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("/opt/catalog/release-manifest.json"))
    parser.add_argument("--context-root", type=Path, help="Verify staged context paths locally instead of image_path")
    parser.add_argument("--require-hosted", action="store_true")
    args = parser.parse_args()
    try:
        with redirect_stdout(io.StringIO()):
            result = verify_release(args)
        code = 0
    except VerificationError as exc:
        result, code = {"ok": False, "error": str(exc)}, 1
    except Exception as exc:
        # Unexpected exception messages can include driver URLs or arbitrary
        # import errors. Keep diagnostics useful without printing credentials.
        result, code = {"ok": False, "error_type": type(exc).__name__}, 1
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
