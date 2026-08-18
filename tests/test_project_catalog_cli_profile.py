from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest


class _FakeCatalog:
    def list(self):
        return []

    def search(self, *args, **kwargs):
        del args, kwargs
        return []

    def get(self, key):
        return SimpleNamespace(
            key=key,
            kind="adapter",
            title="Example",
            import_path="example:Adapter",
            tags=(),
            summary="",
            companions=(),
            context_requires=(),
            context_provides=(),
            context_mutates=(),
            context_cache=(),
            context_notes=(),
            artifact_requires=(),
            artifact_provides=(),
            phase_in=(),
            phase_out=(),
            use_when=(),
            minimal_wiring=(),
            required_companions=(),
            config_keys=(),
            example_entry="",
        )


@pytest.mark.parametrize(
    ("command", "tail"),
    (
        ("search", ["anything"]),
        ("list", []),
        ("show", ["adapter.example"]),
    ),
)
def test_project_catalog_cli_forwards_profile(
    monkeypatch,
    tmp_path,
    command: str,
    tail: list[str],
) -> None:
    from nsgablack.__main__ import main

    cli_package = main.__module__.rsplit(".", 1)[0]
    project_catalog = importlib.import_module(f"{cli_package}.project.catalog")

    seen = {}
    monkeypatch.setattr(project_catalog, "find_project_root", lambda path: tmp_path)

    def fake_load_project_catalog(root, *, include_global=False, profile=None):
        seen.update(root=root, include_global=include_global, profile=profile)
        return _FakeCatalog()

    monkeypatch.setattr(project_catalog, "load_project_catalog", fake_load_project_catalog)

    code = main(
        [
            "project",
            "catalog",
            command,
            *tail,
            "--path",
            str(tmp_path),
            "--global",
            "--profile",
            "framework-core",
        ]
    )

    assert code == 0
    assert seen == {
        "root": tmp_path,
        "include_global": True,
        "profile": "framework-core",
    }
