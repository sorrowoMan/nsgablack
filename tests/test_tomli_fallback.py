from __future__ import annotations

import subprocess
import sys


def test_tomli_fallback_for_project_and_catalog_registry():
    code = r"""
import builtins
import os
import sys
import tempfile
import types
from pathlib import Path

orig_import = builtins.__import__

def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "tomllib":
        raise ImportError("blocked tomllib for fallback test")
    return orig_import(name, globals, locals, fromlist, level)

fake_tomli = types.ModuleType("tomli")

def fake_loads(raw: str):
    if "project_case" in raw:
        return {
            "entry": [
                {
                    "key": "project.bias.fallback_probe",
                    "title": "FallbackProbeBias",
                    "kind": "bias",
                    "import_path": "bias.template_bias:BiasTemplate",
                }
            ]
        }
    if "catalog_case" in raw:
        return {
            "entry": [
                {
                    "key": "tool.fallback_probe",
                    "title": "FallbackProbeTool",
                    "kind": "tool",
                    "import_path": "nsgablack.tools.check_repo_root_hygiene:main",
                }
            ]
        }
    return {"entry": []}

fake_tomli.loads = fake_loads
sys.modules["tomli"] = fake_tomli
builtins.__import__ = blocked_import

try:
    import nsgablack.project.catalog as project_catalog
    import nsgablack.catalog.registry as registry

    assert project_catalog._toml is fake_tomli
    assert registry._toml is fake_tomli

    root = Path(tempfile.mkdtemp(prefix="tomli_project_"))
    (root / "catalog").mkdir(parents=True, exist_ok=True)
    (root / "catalog" / "entries.toml").write_text("project_case", encoding="utf-8")
    rows = project_catalog._load_project_toml_entries(root)
    assert rows and rows[0].key == "project.bias.fallback_probe"

    catalog_file = root / "catalog_fallback.toml"
    catalog_file.write_text("catalog_case", encoding="utf-8")
    os.environ["NSGABLACK_CATALOG_PATH"] = str(catalog_file)
    cat = registry.get_catalog(refresh=True)
    assert cat.get("tool.fallback_probe") is not None
finally:
    builtins.__import__ = orig_import
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
