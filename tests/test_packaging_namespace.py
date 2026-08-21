from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_distribution_only_declares_nsgablack_package_namespace() -> None:
    payload = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    setuptools = payload["tool"]["setuptools"]

    packages = tuple(setuptools["packages"])
    assert packages
    assert all(name == "nsgablack" or name.startswith("nsgablack.") for name in packages)

    package_dirs = dict(setuptools["package-dir"])
    assert package_dirs["nsgablack"] == "nsgablack"
    assert all(name == "nsgablack" or name.startswith("nsgablack.") for name in package_dirs)
    assert not {"core", "plugins", "project", "utils"}.intersection(packages)


def test_every_explicit_distribution_package_is_a_regular_package() -> None:
    payload = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    setuptools = payload["tool"]["setuptools"]
    package_dirs = dict(setuptools["package-dir"])
    missing: list[str] = []
    for package in setuptools["packages"]:
        direct = package_dirs.get(package)
        if direct is not None:
            path = ROOT / direct
        else:
            parent = max(
                (name for name in package_dirs if package.startswith(f"{name}.")),
                key=len,
            )
            suffix = package[len(parent) + 1 :].split(".")
            path = ROOT / package_dirs[parent]
            for part in suffix:
                path /= part
        if not (path / "__init__.py").is_file():
            missing.append(package)

    assert missing == []


def test_catalog_document_registry_lives_inside_distribution_package() -> None:
    assert (ROOT / "nsgablack" / "docs_registry.py").is_file()
    assert not (ROOT / "docs_registry.py").exists()
    assert not (ROOT / "nsgablack" / "examples_registry.py").exists()


def test_installed_catalog_shape_omits_repository_only_examples_and_docs(
    tmp_path,
) -> None:
    from nsgablack.catalog.registry import _builtin_catalog_paths

    entries = tmp_path / "catalog" / "entries"
    entries.mkdir(parents=True)
    component = entries / "adapter.toml"
    document = entries / "doc.toml"
    example = entries / "example.toml"
    component.write_text("", encoding="utf-8")
    document.write_text("", encoding="utf-8")
    example.write_text("", encoding="utf-8")

    assert _builtin_catalog_paths(entries) == (component,)

    (tmp_path / "examples" / "cases").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    assert _builtin_catalog_paths(entries) == (component, document, example)


def test_source_catalog_paths_only_reference_existing_repository_assets() -> None:
    entries_dir = ROOT / "catalog" / "entries"
    missing: list[str] = []
    for path in sorted(entries_dir.glob("*.toml")):
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
        for entry in payload.get("entry", []):
            raw = str(entry.get("example_entry", "") or "").strip()
            if not raw:
                continue
            if raw.startswith("python examples"):
                relative = raw[len("python ") :].replace("\\", "/")
            elif raw.startswith("docs/"):
                relative = raw
            else:
                continue
            if not (ROOT / relative).is_file():
                missing.append(f"{entry.get('key', '<unknown>')}: {relative}")

    assert missing == []


def test_document_registry_only_points_to_existing_source_documents() -> None:
    from nsgablack.docs_registry import DOC_POINTERS

    missing = [
        f"{key}: {relative}"
        for key, relative in DOC_POINTERS.items()
        if not (ROOT / relative).is_file()
    ]

    assert missing == []
