"""Read-only source and UI verification for the cloud workspace client."""
from contextlib import ExitStack
from collections import Counter
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch
import urllib.request


def health(port: int = 18645) -> dict:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/apps/framework-workspace/_stcore/health", timeout=3) as response:
        assert response.status == 200
    return {"ok": True, "health_http": 200}


def verify_editor_assets(directory: Path, files) -> dict:
    """Check packaged editor bytes; this does not execute its JavaScript."""
    required = ("index.html", "editor.css", "editor.bundle.js", "build-manifest.json",
                "THIRD_PARTY_LICENSES.txt")
    rows = {Path(row["image_path"]).resolve(): row for row in files}
    hashes = {}
    for name in required:
        path = (directory / name).resolve()
        assert path in rows and path.is_file(), "editor_asset_missing_" + name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == rows[path]["sha256"], "editor_asset_hash_" + name
        hashes[name] = digest
    built = json.loads((directory / "build-manifest.json").read_text(encoding="utf-8"))
    bundle = (directory / "editor.bundle.js").read_bytes()
    assert built.get("schema") == "nsgablack.workspace-editor-assets/v1", "editor_build_manifest_schema"
    assert built.get("bundle") == "editor.bundle.js", "editor_build_manifest_bundle"
    assert built.get("sha256") == hashes["editor.bundle.js"] and built.get("bytes") == len(bundle), \
        "editor_build_manifest_hash"
    return {"files": hashes, "bundle_bytes": len(bundle), "javascript_executed": False}


def verify(*, app: bool = True) -> dict:
    manifest = json.loads(Path("/opt/workspace/workspace-manifest.json").read_text(encoding="utf-8"))
    for row in manifest["files"]:
        path = Path(row["image_path"])
        assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
    result = {"ok": True, "source_files": len(manifest["files"]),
              "source_digest": manifest["source_digest"], "execution_mode": "remote_agent"}
    result["editor_assets"] = verify_editor_assets(
        Path("/opt/src/nsgablack/catalog/workspace_editor_frontend"), manifest["files"])
    result["editor_validation_mode"] = "assets_only"
    if not app:
        return result
    import_started = perf_counter()
    from nsgablack.catalog import lab_workspace, lab_workspace_transport
    from streamlit.testing.v1 import AppTest
    import_seconds = round(perf_counter() - import_started, 4)
    from nsgablack.catalog.curation_provider import DeepSeekGenerator
    calls = {"local_runtime": 0, "process": 0, "remote_mutation": 0, "model": 0}
    rpc = []
    timings = {}
    phase = "initial"
    readonly_operations = frozenset({"list_sources", "list_workspaces", "get_workspace",
        "get_revision", "list_revisions", "read_file", "parameter_schema", "list_jobs", "get_job"})
    deferred_operations = frozenset({"list_sources", "parameter_schema", "list_jobs", "get_job"})
    rpc_call = lab_workspace_transport.WorkspaceRPCClient.call
    def readonly_rpc(client, operation, arguments):
        if operation not in readonly_operations:
            calls["remote_mutation"] += 1
            raise AssertionError("frontend_readonly_rpc_boundary")
        started = perf_counter()
        value = rpc_call(client, operation, arguments)
        rpc.append({"phase": phase, "operation": operation,
                    "seconds": round(perf_counter() - started, 4),
                    "response_bytes": len(json.dumps(value, ensure_ascii=False).encode("utf-8"))})
        return value

    def forbidden(kind):
        def fail(*args, **kwargs):
            calls[kind] += 1
            raise AssertionError("cloud frontend crossed its client boundary")
        return fail

    with ExitStack() as stack:
        # AppTest cannot drive a custom iframe. This explicitly verifies the
        # Python backend contract; headless acceptance covers actual CodeMirror.
        stack.enter_context(patch.dict(os.environ, {"NSGABLACK_WORKSPACE_PLAINTEXT_EDITOR": "1"}))
        stack.enter_context(patch.object(lab_workspace, "_runtime", forbidden("local_runtime")))
        stack.enter_context(patch("subprocess.Popen", forbidden("process")))
        for method in ("generate", "review", "_complete"):
            stack.enter_context(patch.object(DeepSeekGenerator, method, forbidden("model")))
        stack.enter_context(patch.object(lab_workspace_transport.WorkspaceRPCClient, "call", readonly_rpc))
        # Docker/Streamlit executes this file as __main__, without a package.
        # Importing render_workspace here would hide broken relative imports.
        entry = Path("/opt/src/nsgablack/catalog/lab_workspace_ui.py")
        page = AppTest.from_file(str(entry), default_timeout=90)

        def render(name, action):
            nonlocal phase
            phase = name
            started = perf_counter()
            action()
            timings[name] = round(perf_counter() - started, 4)
            assert not page.exception, "frontend_exception_" + name
            assert not page.error, "frontend_error_" + name

        def operations(name):
            return Counter(row["operation"] for row in rpc if row["phase"] == name)

        def assert_editor_unchanged():
            assert next(item.value for item in page.text_area if item.label == "文件内容") == before, "editor_position_lost"

        render("initial", page.run)
        assert any(item.label == "工作副本" for item in page.selectbox), "workspace_not_loaded"
        assert any(item.label == "文件范围" and item.value == "all" for item in page.radio), "file_scope_not_loaded"
        assert any(str(item.key).startswith("project_workspace::tree::") for item in page.sidebar.button), \
            "sidebar_file_tree_not_loaded"
        assert any(item.label == "工程文件" for item in page.sidebar.selectbox), "quick_file_picker_not_loaded"
        assert not any(item.label == "参数填写方式" for item in page.radio), "parameter_form_should_be_deferred"
        assert not any(item.label == "Case 参数 JSON" for item in page.text_area), "json_should_be_advanced"
        assert not deferred_operations.intersection(operations("initial")), "initial_page_loaded_deferred_data"
        before = next(item.value for item in page.text_area if item.label == "文件内容")

        render("rerun", page.run)
        assert not deferred_operations.intersection(operations("rerun")), "rerun_loaded_deferred_data"
        assert_editor_unchanged()

        assert page.session_state["project_workspace::appearance"] == "dark", "default_workspace_theme"
        for appearance in ("light", "system", "dark"):
            render("appearance_" + appearance, lambda value=appearance:
                next(item for item in page.selectbox if item.label == "界面主题").set_value(value).run())
            assert page.session_state["project_workspace::appearance"] == appearance
            assert_editor_unchanged()
            assert not deferred_operations.intersection(operations("appearance_" + appearance)), "theme_loaded_deferred_data"

        render("run_settings", lambda: next(item for item in page.button if item.label == "试跑设置").click().run())
        assert operations("run_settings")["parameter_schema"] > 0, "parameter_schema_not_requested_on_demand"
        assert not {"list_sources", "list_jobs", "get_job"}.intersection(operations("run_settings")), "run_settings_loaded_unrelated_data"
        assert any(item.label == "参数填写方式" for item in page.radio), "case_parameter_form_not_loaded"
        assert not any(item.label == "Case 参数 JSON" for item in page.text_area), "json_should_be_advanced"
        render("run_settings_close", lambda: page.button(key="project_workspace::close_panel::" +
            page.session_state["project_workspace::workspace"]).click().run())
        assert not any(item.label == "参数填写方式" for item in page.radio), "run_panel_not_closed"
        assert not deferred_operations.intersection(operations("run_settings_close")), "closing_panel_loaded_deferred_data"
        assert_editor_unchanged()

        render("source_dialog", lambda: page.button(key="project_workspace::open_source").click().run())
        assert operations("source_dialog")["list_sources"] > 0, "source_metadata_not_requested_on_demand"
        assert not {"parameter_schema", "list_jobs", "get_job"}.intersection(operations("source_dialog")), "source_dialog_loaded_unrelated_data"
        assert any(item.label == "来源 Project" for item in page.selectbox), "source_picker_not_loaded"
        render("source_dialog_close", lambda: page.button(key="project_workspace::source_close").click().run())
        assert page.session_state["project_workspace::source_dialog"] is False, "source_dialog_flag_not_closed"
        assert not deferred_operations.intersection(operations("source_dialog_close")), "closing_source_loaded_deferred_data"
        # AppTest can retain a dialog fragment's previous element tree after
        # its handler requests the full-app rerun. Verify the application state
        # first, then inspect the tree from an explicit clean app render.
        render("source_dialog_settle", page.run)
        assert not any(item.label == "来源 Project" for item in page.selectbox), "source_dialog_not_closed"
        assert not any(item.key == "project_workspace::source_close" for item in page.button), "source_dialog_button_not_closed"
        assert not deferred_operations.intersection(operations("source_dialog_settle")), "closed_source_loaded_deferred_data"
        assert_editor_unchanged()

        render("component_dialog", lambda: next(item for item in page.button if item.label == "查组件").click().run())
        assert page.session_state["project_workspace::reference::open"] is True, "component_dialog_not_open"
        render("component_search", lambda: next(item for item in page.text_input if item.label == "查组件").set_value("CompositeAdapter").run())
        render("component_detail", lambda: page.button(key="project_workspace::reference::hit::adapter.composite").click().run())
        assert any("CompositeAdapter" in str(item.value) for item in page.code), "usage_code_missing"
        render("component_pin", lambda: page.button(key="project_workspace::reference::pin").click().run())
        assert page.session_state["project_workspace::panel::" + page.session_state["project_workspace::workspace"]] == "reference"
        assert page.session_state["project_workspace::reference::open"] is False, "component_pin_dialog_still_open"
        render("component_panel", page.run)
        assert_editor_unchanged()
        render("component_reopen", lambda: page.button(key="project_workspace::reference_window::" +
            page.session_state["project_workspace::workspace"]).click().run())
        assert page.session_state["project_workspace::reference::open"] is True, "component_dialog_not_open"
        render("component_dialog_close", lambda: page.button(key="project_workspace::reference::close").click().run())
        render("component_panel_close", lambda: page.button(key="project_workspace::reference_back::" +
            page.session_state["project_workspace::workspace"]).click().run())
        for name in ("component_panel", "component_dialog", "component_pin", "component_reopen", "component_search", "component_detail",
                     "component_dialog_close", "component_panel_close"):
            assert not deferred_operations.intersection(operations(name)), "component_lookup_loaded_deferred_data"
        assert_editor_unchanged()
    from nsgablack.catalog.lab_workspace_reference import reference_search
    counts = {profile: reference_search(profile=profile)["catalog_total"]
              for profile in ("default", "framework-core")}
    assert counts["default"] > 0 and counts["framework-core"] > 0
    assert not any(calls.values())
    assert "nsgablack.catalog.lab_workspace_runner" not in sys.modules
    result.update(page_loaded=True, entrypoint="streamlit_file", component_dialog=True,
                  component_panel=True, editor_validation_mode="plaintext_backend_contract",
                  appearances=["dark", "light", "system"], default_appearance="dark",
                  component_catalog=counts, execution_calls=calls, model_calls=0,
                  lazy_initial_load=True, source_dialog=True, run_settings=True,
                  import_seconds=import_seconds, render_seconds=timings, rpc=rpc,
                  rpc_count=len(rpc), rpc_counts=dict(Counter(row["operation"] for row in rpc)),
                  rpc_phase_counts={name: dict(Counter(row["operation"] for row in rpc if row["phase"] == name))
                                    for name in timings})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--port", type=int, default=18645)
    args = parser.parse_args()
    try:
        result = health(args.port) if args.health else verify(app=not args.source_only)
    except AssertionError as exc:
        print(json.dumps({"ok": False, "error_type": "AssertionError", "check": str(exc)}))
        return 1
    except Exception as exc:
        print(json.dumps({"ok": False, "error_type": type(exc).__name__}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
