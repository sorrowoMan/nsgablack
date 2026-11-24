"""Native MCP transport over the existing Project tools; no embedded model."""
from __future__ import annotations

import argparse
from collections import OrderedDict
from copy import deepcopy
import json
from pathlib import Path
from threading import RLock
from uuid import uuid4

from .lab_project_assistant import ProjectAssistantRuntime, TOOLS, _ToolContractError
from .lab_project_sources import ProjectSourceRegistry, ProjectSourceError
from .lab_assistant import AssistantProviderError
from .lab_jobs import LabJobError

NAME = "black-framework"
BASICS_URI = "black-framework://foundations"
INSTRUCTIONS = """BlackBase/NSGABlack/MLBlack 工作入口。先调用 framework_context 取得共同基础。
讨论算法可直接查 framework_api；涉及具体工程，list_projects 后 open_project 获取保存状态与 session_id。
后续工程工具携带该 session_id；工程改变时重新打开，不能沿用旧版本收据。
check_project_edit 默认仅静态检查；有可信验证器时才返回 validation。源码编辑使用宿主编辑工具，
执行使用授权的标准 Project/Case/L0 入口。静态通过不代表运行或数学正确。这里不调用另一个AI。"""


def _current_project_root():
    # Host working directory, not a model-supplied path. Register only its
    # nearest formal ancestor; never expose sibling Projects or import code.
    current = Path.cwd()
    for parent in (current, *current.parents):
        if ProjectSourceRegistry._formal_project(parent):
            return parent
    return None


def _default_sources():
    examples = Path(__file__).resolve().parents[1] / "examples" / "cases"
    roots = {"examples": examples} if examples.is_dir() else {}
    current = _current_project_root()
    if current is not None:
        roots["current"] = current
    return ProjectSourceRegistry(roots, allow_empty=True)


def _definition(name, description, properties=None, required=()):
    return {"name": name, "description": description, "inputSchema": {
        "type": "object", "properties": properties or {}, "required": list(required),
        "additionalProperties": False}}


class FrameworkWorkspace:
    """Per-process sessions; trusted sources/validators are supplied by the host."""

    def __init__(self, sources=None, *, edit_validator=None, validation_identity=None,
                 edit_call_contracts=None):
        self.runtime = ProjectAssistantRuntime(
            sources if sources is not None else _default_sources(),
            edit_validator=edit_validator, validation_identity=validation_identity,
            require_validated_edit=edit_validator is not None,
            edit_call_contracts=edit_call_contracts)
        self.sessions = OrderedDict()
        self.edits = {}
        self._lock = RLock()

    def definitions(self):
        definitions = [
            _definition("framework_context", "取得版本化框架基础、能力及当前使用流程。"),
            _definition("catalog_search", "按算法想法查当前源码Catalog，不导入或构造组件。", {
                "query": {"type": "string", "minLength": 1, "maxLength": 300},
                "profile": {"type": "string", "enum": ["default", "framework-core"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20}}, ("query",)),
            _definition("catalog_show", "查组件角色、入口、配置键与最小装配，不代表已执行。", {
                "key": {"type": "string", "minLength": 1, "maxLength": 240},
                "profile": {"type": "string", "enum": ["default", "framework-core"]}}, ("key",)),
            _definition("list_projects", "列出宿主授权范围内的标准Project；不运行构造器。", {
                "query": {"type": "string", "maxLength": 300},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100}}),
            _definition("open_project", "读取已保存的设计/装配状态，建立版本绑定会话。", {
                "project_id": {"type": "string", "minLength": 1, "maxLength": 240},
                "instruction": {"type": "string", "minLength": 1, "maxLength": 4000}}, ("project_id",)),
            _definition("close_project", "释放已打开的工程会话。", {
                "session_id": {"type": "string"}}, ("session_id",))]
        definitions.append(_definition("edit_result", "交付前核对本版本、该文件最后一次检查；失败复验会撤销旧通过。", {
            "session_id": {"type": "string"}, "path": {"type": "string"},
            "edit_digest": {"type": "string"}}, ("session_id", "path", "edit_digest")))
        for tool in TOOLS:
            item = deepcopy(tool["function"])
            if item["name"] == "project_result":
                continue
            schema = item.pop("parameters")
            # Global API lookup is useful before choosing an algorithm Project.
            schema["properties"]["session_id"] = {"type": "string"}
            if item["name"] != "framework_api":
                schema["required"].append("session_id")
            definitions.append({**item, "inputSchema": schema})
        return definitions

    def context(self):
        from .lab_knowledge import read_framework_basics
        from .lab_api import _ROOT as api_root
        from .lab_jobs import spec_digest
        from importlib.metadata import version, PackageNotFoundError
        import hashlib
        versions = {}
        for package in ("blackbase", "nsgablack", "mlblack"):
            try:
                versions[package] = version(package)
            except PackageNotFoundError:
                versions[package] = None
        root = Path(__file__).resolve().parents[1]
        anchors = ("pyproject.toml", "AGENTS.md", "core/composable_solver.py",
                   "adapters/change_pool.py", "units/population_operations.py")
        fingerprints = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                        for name in anchors if (root / name).is_file()}
        source = {"root": str(root), "api_source_root": str(api_root),
                  "representative_sources": fingerprints, "full_tree_attestation": False}
        if (root / "pyproject.toml").is_file():
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            source["source_package_version"] = tomllib.loads(
                (root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
            source["distribution_metadata_matches_source"] = (
                source["source_package_version"] == versions["nsgablack"])
        source["identity"] = spec_digest(source)
        return {"schema": "nsgablack.framework_mcp/v1", "versions": versions,
                "version_evidence_kind": "installed_distribution_metadata_not_source_attestation",
                "framework_source": source,
                "framework_basics": read_framework_basics(), "workflow": INSTRUCTIONS,
                "capabilities": {"model_provider": False, "source_write": False,
                    "isolated_edit_validation": self.runtime.edit_validator is not None,
                    "validation_identity": self.runtime.validation_identity,
                    "source_scope": "host_configured_standard_projects",
                    "project_sessions": 8}}

    def call(self, name, arguments):
        with self._lock:
            return self._call(name, arguments)

    def _call(self, name, arguments):
        from jsonschema import validate
        from jsonschema.exceptions import ValidationError
        definitions = {item["name"]: item for item in self.definitions()}
        if name not in definitions:
            raise ValueError("unknown_tool")
        try:
            validate(arguments, definitions[name]["inputSchema"])
        except ValidationError:
            raise ValueError("invalid_tool_arguments") from None
        arguments = deepcopy(arguments)
        if name == "framework_context":
            return self.context()
        if name in {"catalog_search", "catalog_show"}:
            from .registry import get_source_catalog
            from .lab_jobs import spec_digest
            profile = arguments.get("profile", "framework-core")
            catalog = get_source_catalog(profile=profile)
            entries = (catalog.search(arguments["query"], limit=arguments.get("limit", 10))
                       if name == "catalog_search" else [catalog.get(arguments["key"])])
            fields = ("key", "title", "kind", "import_path", "summary", "config_keys",
                      "minimal_wiring", "required_companions", "example_entry")
            rows = [{field: getattr(entry, field) for field in fields} for entry in entries if entry is not None]
            return {"profile": profile, "source": "framework_source_catalog", "entries": rows,
                    "result_digest": spec_digest({"entries": rows}), "execution_evidence": False}
        if name == "list_projects":
            return self.runtime.sources.browse_projects(arguments.get("query", ""), limit=arguments.get("limit", 20))
        if name == "open_project":
            packet = self.runtime.prepare({"project_id": arguments["project_id"],
                "instruction": arguments.get("instruction", "继续当前Project的算法设计与装配"), "history": []})
            self.runtime._verify_project_state(packet)
            session = uuid4().hex
            self.sessions[session] = packet
            if len(self.sessions) > 8:
                expired, _ = self.sessions.popitem(last=False)
                self.edits.pop(expired, None)
            self.edits[session] = OrderedDict()
            return {"session_id": session, "project": packet["project"],
                    "project_state": packet["project_state"],
                    "framework_context": packet["framework_context"],
                    "framework_basics": self.context()["framework_basics"],
                    "edit_validation": self.runtime._edit_validation_profile(),
                    "edit_call_contracts": packet.get("edit_call_contracts"),
                    "source_write": False}
        session = arguments.pop("session_id", None)
        if name == "close_project":
            self.edits.pop(session, None)
            return {"closed": self.sessions.pop(session, None) is not None}
        if session is None and name == "framework_api" and not arguments.get("project_path"):
            from .lab_api import inspect_framework_api, verify_api_sources
            result = inspect_framework_api(arguments["symbol"], member=arguments.get("member"))
            verify_api_sources(result)
            return result
        if session not in self.sessions:
            raise ValueError("project_session_missing_or_expired")
        packet = self.sessions[session]
        if name == "edit_result":
            self.runtime._verify_project_state(packet)
            result = self.edits[session].get(arguments["path"])
            if result is None or result["edit_digest"] != arguments["edit_digest"]:
                raise ValueError("edit_result_missing_or_superseded")
            return {"result": deepcopy(result), "applied": False,
                    "verification_status": ("passed" if self.runtime._validated_edit(result)
                        else "failed" if result["check"]["status"] == "rejected"
                        or result.get("validation", {}).get("status") in {"passed", "failed"}
                        else "not_run")}
        if name == "check_project_edit":
            # Remove prior authority before dispatch, including exception paths.
            self.edits[session].pop(arguments["path"], None)
        result = self.runtime.execute_tool(name, arguments, packet)
        if name == "check_project_edit":
            self.edits[session][arguments["path"]] = deepcopy(result)
            if len(self.edits[session]) > 32:
                self.edits[session].popitem(last=False)
        self.sessions.move_to_end(session)
        return result


def create_server(workspace):
    # Optional dependency: importing core/framework code does not require MCP.
    from mcp.server import Server
    from mcp import types

    async def list_tools(_ctx, _params):
        tools = []
        for item in workspace.definitions():
            executes = item["name"] == "check_project_edit" and workspace.runtime.edit_validator is not None
            tools.append(types.Tool(**item, annotations=types.ToolAnnotations(
                read_only_hint=not executes, destructive_hint=False,
                idempotent_hint=item["name"] not in {"open_project", "close_project", "check_project_edit"},
                open_world_hint=False)))
        return types.ListToolsResult(tools=tools)

    async def call_tool(_ctx, params):
        import anyio
        try:
            result = await anyio.to_thread.run_sync(lambda: workspace.call(params.name, params.arguments or {}))
            error = False
        except Exception as exc:
            # Never put arbitrary exception text/host paths/credentials on wire.
            if isinstance(exc, (ProjectSourceError, LabJobError)):
                code = exc.code
            elif isinstance(exc, AssistantProviderError):
                code = str(exc) if str(exc).startswith("ai_") else "framework_tool_failed"
            elif isinstance(exc, ValueError) and str(exc) in {
                    "invalid_tool_arguments", "unknown_tool", "project_session_missing_or_expired",
                    "edit_result_missing_or_superseded"}:
                code = str(exc)
            else:
                code = "framework_tool_failed"
            public_error = (deepcopy(exc.feedback) if isinstance(exc, _ToolContractError) else
                {"code": code, "message": "工具未完成；版本变化请重新open_project，其余按声明参数修正。"})
            result, error = {"error": public_error}, True
        return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, allow_nan=False))],
                                    structuredContent=result, isError=error)

    async def list_resources(_ctx, _params):
        return types.ListResourcesResult(resources=[types.Resource(
            uri=BASICS_URI, name="框架基础认识", mimeType="text/markdown")])

    async def read_resource(_ctx, params):
        if str(params.uri) != BASICS_URI:
            raise ValueError("unknown_resource")
        from .lab_knowledge import read_framework_basics
        return types.ReadResourceResult(contents=[types.TextResourceContents(
            uri=BASICS_URI, mimeType="text/markdown", text=read_framework_basics()["content"])])

    return Server(NAME, version="1.0.0", instructions=INSTRUCTIONS,
        on_list_tools=list_tools, on_call_tool=call_tool,
        on_list_resources=list_resources, on_read_resource=read_resource)


async def serve_stdio(workspace):
    from mcp.server.stdio import stdio_server
    server = create_server(workspace)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main(argv=None):
    parser = argparse.ArgumentParser(description="Black Framework原生stdio MCP；不调用模型服务")
    parser.add_argument("--project-root", action="append", default=[], metavar="NAME=PATH",
                        help="宿主授权的标准Project或其直接父目录；可重复")
    parser.add_argument("--include-current-project", action="store_true",
                        help="宿主显式允许将工作目录所属的最近标准Project加入现有根目录")
    parser.add_argument("--validation-factory", metavar="MODULE:FACTORY",
                        help="宿主明确配置的可信工厂，返回edit_validator/validation_identity/可选edit_call_contracts")
    parser.add_argument("--expected-framework-root", type=Path,
                        help="可选的宿主源码归属断言；实际MCP不来自该目录时拒绝启动")
    args = parser.parse_args(argv)
    if (args.expected_framework_root is not None
            and args.expected_framework_root.resolve() != Path(__file__).resolve().parents[1]):
        parser.error("framework_source_root_mismatch: 当前Python加载了另一份框架源码")
    roots = {}
    for item in args.project_root:
        name, sep, path = item.partition("=")
        if not sep or name in roots:
            parser.error("--project-root应为唯一NAME=PATH")
        roots[name] = Path(path)
    binding = {}
    if args.validation_factory:
        import importlib
        module, sep, factory = args.validation_factory.partition(":")
        if not sep or not factory.isidentifier():
            parser.error("--validation-factory应为MODULE:FACTORY")
        binding = getattr(importlib.import_module(module), factory)()
        if (not isinstance(binding, dict) or set(binding) - {
                "edit_validator", "validation_identity", "edit_call_contracts"}
                or not callable(binding.get("edit_validator"))
                or not isinstance(binding.get("validation_identity"), str)):
            parser.error("可信验证工厂应返回可调用验证器与非空验收身份")
    sources = ProjectSourceRegistry(roots) if roots else _default_sources()
    if args.include_current_project:
        current = _current_project_root()
        if current is not None:
            configured = sources.roots.get("current")
            if configured is not None and configured != current:
                parser.error("current_project_root_conflict: 名称current已绑定其他目录；请重命名显式根目录")
            sources = ProjectSourceRegistry({**sources.roots, "current": current})
    workspace = FrameworkWorkspace(sources, **binding)

    import anyio
    anyio.run(serve_stdio, workspace)


if __name__ == "__main__":
    main()
