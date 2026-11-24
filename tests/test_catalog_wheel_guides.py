"""Check the public guide closure in the installed package layout."""
from __future__ import annotations

from pathlib import Path
import shutil
try:
    import tomllib
except ImportError:  # Python 3.10
    import tomli as tomllib

from nsgablack.catalog.examples import _snippet


ROOT = Path(__file__).resolve().parents[1]


def _guide_sources():
    for manifest in sorted((ROOT / "catalog/example_manifests").glob("*.toml")):
        records = tomllib.loads(manifest.read_text(encoding="utf-8-sig")).get("example", [])
        for record in records:
            for source in record.get("sources", []):
                if source["path"].startswith("nsgablack/docs/catalog_usage/"):
                    yield source


def _packaged_guides():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8-sig"))
    patterns = metadata["tool"]["setuptools"]["package-data"]["nsgablack.catalog"]
    return {path.resolve() for pattern in patterns for path in (ROOT / "catalog").glob(pattern)
            if path.is_file()}


def test_wheel_declares_every_focused_public_guide_source():
    required = {ROOT / source["path"].split("/", 1)[1] for source in _guide_sources()}
    assert required, "The manifest must contain focused public documentation."
    missing = required - _packaged_guides()
    assert not missing, "Guide sources absent from wheel package-data: " + ", ".join(
        str(path.relative_to(ROOT)) for path in sorted(missing))


def test_guide_sections_remain_readable_without_the_checkout(tmp_path):
    # Wheels map ../docs/... from catalog/ to site-packages/nsgablack/docs/...
    # Exercise that layout using only resources selected by package-data.
    installed = tmp_path / "site-packages/nsgablack"
    for source in _packaged_guides():
        relative = source.relative_to(ROOT)
        if relative.parts[:2] != ("docs", "catalog_usage"):
            continue
        destination = installed / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    sources = list(_guide_sources())
    assert sources
    for source in sources:
        snippet = _snippet({"nsgablack": installed}, source)
        assert snippet["text"].strip(), source
        assert snippet["file_sha256"], source
    assert not (installed / "examples").exists()
