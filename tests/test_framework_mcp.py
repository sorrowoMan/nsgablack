import hashlib
import json
from pathlib import Path
import sys

import anyio
import pytest

pytest.importorskip("mcp")
from mcp import Client, StdioServerParameters
from nsgablack.catalog.assistant_session_acceptance import create_teaching_project
from nsgablack.catalog.mcp_server import FrameworkWorkspace
from nsgablack.catalog.lab_project_sources import ProjectSourceRegistry


def test_framework_without_project_roots_can_still_supply_api():
    workspace = FrameworkWorkspace(ProjectSourceRegistry({}, allow_empty=True))
    assert workspace.call("list_projects", {})["projects"] == []
    assert workspace.call("framework_context", {})["framework_basics"]["content"]
    assert workspace.call("framework_api", {"symbol": "nsgablack.units.PopulationUnit"})["status"] == "found"


def test_default_sources_find_only_current_project_ancestor_without_importing_it(tmp_path, monkeypatch):
    from nsgablack.catalog.mcp_server import _default_sources
    sources, project_id = create_teaching_project(tmp_path / "active")
    project = sources.resolve_project(project_id)
    (project / "project_config.py").write_text("raise AssertionError('must not import')\n", encoding="utf-8")
    create_teaching_project(tmp_path / "sibling")
    monkeypatch.chdir(project / "cases/hybrid_search")
    discovered = _default_sources()
    assert discovered.resolve_project("current:.") == project
    assert discovered.roots["current"] == project
    assert all(path != tmp_path for path in discovered.roots.values())
    assert [key for key in discovered._projects() if key.startswith("current:")] == ["current:."]


@pytest.mark.parametrize("include_current", (False, True))
def test_explicit_roots_require_host_opt_in_before_adding_working_project(tmp_path, monkeypatch, include_current):
    import nsgablack.catalog.mcp_server as module
    active_sources, project_id = create_teaching_project(tmp_path / "active")
    active = active_sources.resolve_project(project_id)
    other_sources, other_id = create_teaching_project(tmp_path / "other")
    other = other_sources.resolve_project(other_id)
    monkeypatch.chdir(active / "cases/hybrid_search")
    captured = []
    async def inspect_workspace(workspace):
        captured.append(workspace.runtime.sources.roots)
    monkeypatch.setattr(module, "serve_stdio", inspect_workspace)
    args = ["--project-root", "limited=" + str(other)]
    if include_current:
        args.append("--include-current-project")
    module.main(args)
    assert captured[0]["limited"] == other
    assert (captured[0].get("current") == active) is include_current


def test_explicit_current_alias_cannot_silently_point_to_another_project(tmp_path, monkeypatch):
    import nsgablack.catalog.mcp_server as module
    def project(name):
        path=tmp_path/name
        (path/"cases").mkdir(parents=True)
        for file in ("project_config.py", "run_project.py", "cases/__init__.py"):
            (path/file).write_text("", encoding="utf-8")
        return path
    active, other=project("active"), project("other")
    monkeypatch.chdir(active)
    with pytest.raises(SystemExit) as exc:
        module.main(["--project-root", "current="+str(other), "--include-current-project"])
    assert exc.value.code == 2


def test_source_binding_distinguishes_same_version_checkouts_and_wrong_host_root(tmp_path):
    context = FrameworkWorkspace(ProjectSourceRegistry({}, allow_empty=True)).context()
    binding = context["framework_source"]
    assert Path(binding["root"]).resolve() == Path(__file__).resolve().parents[1]
    assert binding["root"] == binding["api_source_root"]
    path = Path(binding["root"]) / "units/population_operations.py"
    assert binding["representative_sources"]["units/population_operations.py"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert binding["full_tree_attestation"] is False
    from nsgablack.catalog.mcp_server import main
    with pytest.raises(SystemExit) as error:
        main(["--expected-framework-root", str(tmp_path)])
    assert error.value.code == 2


def test_workspace_rejects_drift_and_cannot_install_validator(tmp_path):
    sources, project_id = create_teaching_project(tmp_path)
    workspace = FrameworkWorkspace(sources)
    opened = workspace.call("open_project", {"project_id": project_id})
    session = opened["session_id"]
    assert opened["source_write"] is False
    assert opened["edit_validation"]["enabled"] is False
    with pytest.raises(ValueError, match="invalid_tool_arguments"):
        workspace.call("open_project", {"project_id": project_id, "edit_validator": "anything"})
    with pytest.raises(ValueError, match="project_session_missing"):
        workspace.call("project_read", {"session_id": "wrong", "path": "README.md"})
    with pytest.raises(ValueError):
        workspace.call("project_read", {"session_id": session, "path": "../AGENTS.md"})
    (tmp_path / "session_design" / "DESIGN.md").write_text("# changed", encoding="utf-8")
    with pytest.raises(Exception, match="ai_project_context_mismatch"):
        workspace.call("project_read", {"session_id": session, "path": "README.md"})
    reopened = workspace.call("open_project", {"project_id": project_id})
    assert reopened["project"]["source_digest"] != opened["project"]["source_digest"]
    assert workspace.call("close_project", {"session_id": session}) == {"closed": True}


def test_trusted_validator_still_cannot_return_another_sources_receipt(tmp_path):
    sources, project_id = create_teaching_project(tmp_path)
    workspace = FrameworkWorkspace(sources, edit_validator=lambda p: {
        "status": "passed", "executed": True, "code_sha256": "0" * 64,
        "executed_source_sha256": "0" * 64, "validation_identity": "fixed/v1"},
        validation_identity="fixed/v1")
    session = workspace.call("open_project", {"project_id": project_id})["session_id"]
    with pytest.raises(ValueError, match="project_edit_validation_unbound"):
        workspace.call("check_project_edit", {"session_id": session,
            "path": "cases/hybrid_search/adapter/new_ops.py", "source": "def op(x):\n    return x\n"})


def test_last_failed_check_revokes_the_same_source_previous_pass(tmp_path):
    sources, project_id = create_teaching_project(tmp_path)
    passed = True
    def validate(p):
        return {"status": "passed" if passed else "failed", "executed": True,
                "code_sha256": p["code_sha256"], "executed_source_sha256": p["code_sha256"],
                "validation_identity": "fixed/v1"}
    workspace = FrameworkWorkspace(sources, edit_validator=validate, validation_identity="fixed/v1")
    session = workspace.call("open_project", {"project_id": project_id})["session_id"]
    args = {"session_id": session, "path": "cases/hybrid_search/adapter/new_ops.py", "source": "def op(x):\n    return x\n"}
    first = workspace.call("check_project_edit", args)
    lookup = {"session_id": session, "path": args["path"], "edit_digest": first["edit_digest"]}
    assert workspace.call("edit_result", lookup)["verification_status"] == "passed"
    passed = False
    workspace.call("check_project_edit", args)
    assert workspace.call("edit_result", lookup)["verification_status"] == "failed"


def test_validation_not_run_is_not_reported_as_failed_or_passed(tmp_path):
    sources, project_id = create_teaching_project(tmp_path)
    workspace = FrameworkWorkspace(sources, edit_validator=lambda p: {
        "status": "not_run", "executed": False, "code_sha256": p["code_sha256"]},
        validation_identity="fixed/v1")
    session = workspace.call("open_project", {"project_id": project_id})["session_id"]
    path = "cases/hybrid_search/adapter/new_ops.py"
    result = workspace.call("check_project_edit", {"session_id": session, "path": path,
        "source": "def op(x):\n    return x\n"})
    assert workspace.call("edit_result", {"session_id": session, "path": path,
        "edit_digest": result["edit_digest"]})["verification_status"] == "not_run"


def test_stdio_real_tools_and_source_bound_validation_loop(tmp_path):
    _sources, project_id = create_teaching_project(tmp_path)
    # Real native MCP process; the host binds the existing fixed, isolated Case
    # validator. Neither the model nor tool arguments can install a callback.
    program = "\n".join([
        "import anyio",
        "from nsgablack.catalog.mcp_server import FrameworkWorkspace, serve_stdio",
        "from nsgablack.catalog.lab_project_sources import ProjectSourceRegistry",
        "from nsgablack.catalog.assistant_novel_acceptance import execute_candidate, spec_identity",
        f"sources=ProjectSourceRegistry({{'acceptance': {str(tmp_path)!r}}})",
        "workspace=FrameworkWorkspace(sources, edit_validator=lambda p: execute_candidate(p, 'age_population_unit'), validation_identity=spec_identity())",
        "anyio.run(serve_stdio, workspace)",
    ])
    repo = Path(__file__).resolve().parents[1]
    evidence = repo / "docs/user_guide/evidence"
    names = ["ai-novel-20261123.unit-continuation-v2.age_population_unit.check1.py",
             "ai-novel-20261123.unit-continuation-v2.age_population_unit.check2.py"]
    sources = [(evidence / name).read_text(encoding="utf-8") for name in names]
    assert hashlib.sha256(sources[1].encode()).hexdigest() == "94d4d68c6bf6871fc1cbb8e406a9d7161a17a4a5752b33a93f4bf239908281a7"

    async def exercise():
        async with Client(StdioServerParameters(command=sys.executable, args=["-c", program]),
                          read_timeout_seconds=100) as client:
            definitions = await client.list_tools()
            assert "framework_api" in [item.name for item in definitions.tools]
            annotations = {item.name: item.annotations for item in definitions.tools}
            assert annotations["framework_context"].read_only_hint is True
            assert annotations["check_project_edit"].read_only_hint is False
            trace = []
            async def call(name, args=None):
                result = await client.call_tool(name, args or {})
                assert not result.is_error, result
                trace.append({"tool": name, "result_sha256": hashlib.sha256(
                    json.dumps(result.structured_content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()})
                return result.structured_content
            context = await call("framework_context")
            assert "Pool" in context["framework_basics"]["content"]
            assert context["capabilities"]["model_provider"] is False
            for profile in ("default", "framework-core"):
                found = await call("catalog_search", {"query": "framework_mcp", "profile": profile})
                assert found["entries"][0]["key"] == "tool.framework_mcp"
                assert found["execution_evidence"] is False
            entry = await call("catalog_show", {"key": "tool.framework_mcp"})
            assert entry["entries"][0]["import_path"].endswith(":FrameworkWorkspace")
            resource = await client.read_resource("black-framework://foundations")
            assert "Unit" in resource.contents[0].text
            choices = await call("list_projects")
            assert project_id in [p["project_id"] for p in choices["projects"]]
            opened = await call("open_project", {"project_id": project_id})
            assert opened["project_state"]["excerpts"]
            session = opened["session_id"]
            schema = await call("framework_api", {"symbol": "nsgablack.units.collections.PopulationUnit", "member": "schema"})
            assert schema["member"]["value_contract"]["runtime_validated"] is False
            bound = await call("framework_api", {"session_id": session,
                "symbol": "nsgablack.units.collections.PopulationUnit", "member": "schema"})
            assert bound == schema
            rejected = await client.call_tool("project_read", {"session_id": session, "path": "../key.pem"})
            assert rejected.is_error
            path = "cases/hybrid_search/adapter/novel_ops.py"
            first = await call("check_project_edit", {"session_id": session, "path": path, "source": sources[0]})
            assert first["validation"]["status"] == "failed"
            assert first["validation"]["error"] == "Population member field age must align with rows"
            second = await call("check_project_edit", {"session_id": session, "path": path, "source": sources[1]})
            assert second["validation"]["status"] == "passed"
            assert second["validation"]["executed_source_sha256"] == second["code_sha256"]
            assert second["validation"]["formal_case"]["evaluations"] == 7
            assert second["validation"]["partial_acceptance"]["committed_steps"] == 2
            assert second["validation"]["failed_step_rollback"]["committed_steps"] == 1
            delivery = await call("edit_result", {"session_id": session, "path": path,
                "edit_digest": second["edit_digest"]})
            assert delivery["verification_status"] == "passed"
            assert not (tmp_path / "session_design" / path).exists()
            closed = await call("close_project", {"session_id": session})
            assert closed["closed"] is True
            (tmp_path / "mcp-proof.json").write_text(json.dumps({
                "kind": "native_stdio_mcp_fixed_source_replay", "model_HTTP_calls": 0,
                "new_model_generation": False, "project_id": project_id,
                "framework_basics": context["framework_basics"]["metadata"],
                "versions": context["versions"], "tool_trace": trace,
                "failed_source": first, "corrected_source": second,
                "original_project_modified": False}, ensure_ascii=False, indent=2), encoding="utf-8")
    anyio.run(exercise)
