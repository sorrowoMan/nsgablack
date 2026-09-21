from __future__ import annotations

from pathlib import Path
import re

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib


REPO_ROOT = Path(__file__).resolve().parents[1]


def _source_version(path: Path) -> str:
    match = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)["\']',
        path.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    assert match is not None, f"missing __version__ in {path}"
    return match.group(1)


def test_source_and_wheel_package_versions_match_build_metadata():
    project_version = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]

    assert _source_version(REPO_ROOT / "__init__.py") == project_version
    assert _source_version(REPO_ROOT / "nsgablack" / "__init__.py") == project_version


def test_stable_top_level_imports():
    import nsgablack

    assert isinstance(nsgablack.__version__, str)
    assert callable(nsgablack.get_catalog)


def test_stable_catalog_entry_points_importable():
    # The project treats catalog + plugin/adapters as the stable entry path.
    from nsgablack.catalog import get_catalog

    c = get_catalog()
    assert c.get("suite.benchmark_harness") is None
    assert c.get("plugin.benchmark_harness") is not None
    assert c.get("plugin.module_report") is not None


def test_profiler_plugin_importable():
    from nsgablack.plugins import ProfilerPlugin

    assert ProfilerPlugin is not None


def test_public_state_protocols_importable():
    from nsgablack.adapters import PopulationPartition
    from nsgablack.core import RunProgressState

    assert PopulationPartition is not None
    assert RunProgressState is not None


