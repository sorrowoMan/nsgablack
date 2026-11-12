"""Source-only deployment closure, including the optional public ML Catalog."""
import importlib.util
import json
from pathlib import Path
import tarfile
import pytest


def _packager():
    path = Path(__file__).resolve().parents[1] / "deployment/catalog/package_context.py"
    spec = importlib.util.spec_from_file_location("catalog_package_context_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("include_asset", [False, True])
def test_deployment_context_carries_three_sources_and_excludes_secrets(tmp_path, include_asset):
    packager = _packager()
    nsga, base, ml = (tmp_path / name for name in ("nsgablack", "blackbase", "mlblack"))
    files = {
        nsga: ("__init__.py", "catalog/entries/core_architecture.toml", "catalog/guidance.py",
               "docs/architecture/CATALOG_USAGE_CN.md", "catalog/dashboard.py", "catalog/dashboard_shell.py"),
        base: ("README.md", "src/blackbase/catalog.py"),
        ml: ("__init__.py", "context_keys.py", "cli.py", "catalog/registry.py", "catalog/entries/codec.toml"),
    }
    for root, names in files.items():
        root.mkdir()
        (root / "pyproject.toml").write_text('[project]\nversion="0.0.1"\n', encoding="utf-8")
        for name in names:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# public source\n", encoding="utf-8")
    for name in ("Dockerfile", "requirements-web.txt", "README.md", "package_context.py", "verify_release.py", "verify_ui.py", "verify_knowledge.py", "verify_search_filters.py",
                 "verify_examples.py", "verify_navigation.py", "verify_lab.py", "verify_lab_ai.py",
                 "build_examples.py", "run_example_receipts.py", "runtime.py", "auto_curate.py", "complete_catalog.py", "completion_worker.py", "gateway.conf", "verify_gateway.py"):
        path = nsga / "deployment/catalog" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# deployment source\n", encoding="utf-8")
    # Denied paths are discarded before reading even credential-shaped content.
    for name in ("catalog/db.toml.local", "catalog/.env", "catalog/secret.pem", "examples/data/private.py"):
        path = ml / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("-----BEGIN PRIVATE KEY-----", encoding="utf-8")
    case = nsga / "examples/cases/demo/cases/search"
    case.mkdir(parents=True)
    (case / "__init__.py").write_text("", encoding="utf-8")
    (case / "build_solver.py").write_text("# trusted Case entry\n", encoding="utf-8")
    (case.parent / "__init__.py").write_text("", encoding="utf-8")
    (case.parent.parent / "project_config.py").write_text("STAGES = []\n", encoding="utf-8")
    (case.parent.parent / "run_project.py").write_text("# formal Project entry\n", encoding="utf-8")
    (case / "supply.csv").write_text("material,day0\n1,10\n", encoding="utf-8")
    asset = "examples/cases/demo/cases/search/supply.csv"
    archive = packager.build_context(nsga, base, tmp_path / "output", mlblack=ml,
                                    project_assets=(asset,) if include_asset else ())
    with tarfile.open(archive) as source:
        manifest = json.load(source.extractfile("release-manifest.json"))
        names = set(source.getnames())
    assert "mlblack/context_keys.py" in names
    assert "mlblack/catalog/entries/codec.toml" in names
    assert set(manifest["versions"]) == {"nsgablack", "blackbase", "mlblack"}
    assert all("private" not in name and "db.toml" not in name and not name.endswith((".env", ".pem")) for name in names)
    ml_record = next(item for item in manifest["files"] if item["path"] == "mlblack/catalog/registry.py")
    assert ml_record["image_path"] == "/opt/src/mlblack/catalog/registry.py"
    assert ("nsgablack/" + asset in names) is include_asset
    assert manifest["policy"]["explicit_project_assets"] == ([asset] if include_asset else [])
    if include_asset:
        for rejected in ("../private.csv", "examples/cases/demo/cases/search/secret.csv",
                         "catalog/supply.csv", "examples/cases/demo/cases/search/run.py"):
            with pytest.raises(ValueError):
                packager.build_context(nsga, base, tmp_path / "rejected", mlblack=ml,
                                        project_assets=(rejected,))


def test_ml_navigation_and_payload_preserve_public_source_identity():
    from nsgablack.catalog.dashboard import _catalog_kind_from_target, _source_badges
    from nsgablack.catalog.facade import _entry_payload
    from nsgablack.catalog.registry import CatalogEntry

    entry = CatalogEntry(key="mlblack.codec.test", title="ML codec", kind="codec", import_path="builtins:len",
                         metadata={"catalog_framework": "mlblack", "catalog_original_key": "codec.test"})
    payload = _entry_payload(entry)
    assert payload["metadata"] == entry.metadata
    assert "mlblack" in _source_badges(payload, {})
    assert _catalog_kind_from_target(target_key=entry.key) == "codec"
    assert _catalog_kind_from_target(target_key="custom-key", target_kind="head") == "head"


def test_preferred_database_keeps_foreign_contracts_without_nsga_inference(monkeypatch):
    from nsgablack.catalog import facade, usage
    from nsgablack.catalog.registry import Catalog, CatalogEntry

    entry = CatalogEntry(key="mlblack.bias.test", title="ML bias", kind="bias", import_path="builtins:len",
                         metadata={"catalog_framework": "mlblack"}, contract={"model": {"layout": "test"}})
    monkeypatch.setattr(facade, "get_source_catalog", lambda **kwargs: Catalog([entry]))

    def native_entries_only(entries, **kwargs):
        assert not any(item.metadata.get("catalog_framework") == "mlblack" for item in entries)
        return list(entries)

    monkeypatch.setattr(usage, "enrich_context_contracts", native_entries_only)
    monkeypatch.setattr(usage, "enrich_usage_contracts", native_entries_only)
    route = facade.CatalogReadRoute(profile="default", source_mode="prefer", effective_source="mysql", db_store=None)
    assert facade._enrich_preferred_db_entries([entry], route=route) == [entry]


def _gateway_verifier():
    path = Path(__file__).resolve().parents[1] / "deployment/catalog/verify_gateway.py"
    spec = importlib.util.spec_from_file_location("catalog_gateway_verifier_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _gateway_fixture_ports():
    return {8080: 41000, 8615: 41001, 8089: 41002, 8086: 41003, 8619: 41004, 8643: 41005}


def test_gateway_fixture_replaces_both_application_targets_and_every_listener():
    verifier = _gateway_verifier()
    original = Path(verifier.__file__).with_name("gateway.conf").read_text(encoding="utf-8")
    rewritten = verifier.fixture_config(original, _gateway_fixture_ports())
    assert "127.0.0.1:41004" in rewritten and "127.0.0.1:41005" in rewritten
    assert "listen 127.0.0.1:41000" in rewritten and "listen 127.0.0.1:41001" in rewritten
    assert "default 41002; 41001 41003;" in rewritten
    assert all(f"127.0.0.1:{port}" not in rewritten for port in _gateway_fixture_ports())
    assert set(verifier.APPS) == {"catalog", "workspace"}
    assert len(verifier.AUTH_PATHS) == 2


@pytest.mark.parametrize("replacement", ["http://127.0.0.1:9999", "http://external.invalid:8643"])
def test_gateway_fixture_refuses_unknown_upstreams_instead_of_contacting_them(replacement):
    verifier = _gateway_verifier()
    original = Path(verifier.__file__).with_name("gateway.conf").read_text(encoding="utf-8")
    changed = original.replace("http://127.0.0.1:8643", replacement)
    with pytest.raises(ValueError, match="unexpected gateway.conf listener or upstream"):
        verifier.fixture_config(changed, _gateway_fixture_ports())


@pytest.mark.parametrize("kind", ["missing_workspace", "collision", "production_port"])
def test_gateway_fixture_rejects_missing_or_nonisolated_port_maps(kind):
    verifier = _gateway_verifier()
    original = Path(verifier.__file__).with_name("gateway.conf").read_text(encoding="utf-8")
    ports = _gateway_fixture_ports()
    if kind == "missing_workspace":
        ports.pop(8643)
    elif kind == "collision":
        ports[8643] = ports[8619]
    else:
        ports[8643] = 8643
    with pytest.raises(ValueError, match="invalid isolated fixture endpoints"):
        verifier.fixture_config(original, ports)


def test_workspace_gateway_has_the_same_identity_and_websocket_isolation_as_catalog():
    verifier = _gateway_verifier()
    config = Path(verifier.__file__).with_name("gateway.conf").read_text(encoding="utf-8")

    def location(path):
        return config.split(f"location {path} {{", 1)[1].split("\n        }", 1)[0]

    catalog = location(verifier.BASE)
    workspace = location(verifier.WORKSPACE_BASE)
    assert workspace.replace("/__workspace_access", "/__catalog_access").replace(":8643", ":8619") == catalog
    assert "proxy_pass_request_headers off;" in workspace
    assert "proxy_set_header Cookie $catalog_cookie;" in workspace
    assert "proxy_set_header Sec-WebSocket-Key $http_sec_websocket_key;" in workspace
    assert "proxy_set_header X-Xsrftoken $http_x_xsrftoken;" in workspace
    assert "proxy_set_header Authorization" not in workspace
    assert "proxy_set_header Tailscale-User" not in workspace
    for name in ("catalog", "workspace"):
        auth = location("= /__" + name + "_access")
        assert "internal;" in auth and "proxy_pass_request_body off;" in auth
        assert f"app=framework-{name}&action=read" in auth
