"""Local launcher and remote client selection for Project workspaces.

The hosted Catalog remains a reader. Trusted source roots and writable storage
are selected by the local operator, never by a browser request.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import lru_cache
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT_ENV = "NSGABLACK_PROJECT_WORKSPACE_ROOT"
SOURCES_ENV = "NSGABLACK_PROJECT_WORKSPACE_SOURCES"
REMOTE_ENV = "NSGABLACK_PROJECT_WORKSPACE_CLIENT_CONFIG"
_CLIENT_CONFIGS = (
    "NSGABLACK_LAB_CLIENT_CONFIG", "NSGABLACK_LAB_ASSISTANT_CLIENT_CONFIG",
    "NSGABLACK_PROJECT_RESULT_CLIENT_CONFIG", "NSGABLACK_CATALOG_AI_CONFIG",
    "NSGABLACK_CATALOG_READER_CONFIG", "NSGABLACK_CATALOG_WRITER_CONFIG",
    REMOTE_ENV,
)


@dataclass(frozen=True)
class WorkspaceRuntime:
    store: Any
    runner: Any
    mode: str = "local"


def workspace_enabled(*, hosted: bool = False) -> bool:
    if os.environ.get(REMOTE_ENV, "").strip():
        return True
    return (not hosted and os.environ.get("NSGABLACK_CATALOG_HOSTED") != "1"
            and bool(os.environ.get(ROOT_ENV, "").strip()))


def _source_roots(raw: str):
    if not raw:
        return None
    try:
        roots = json.loads(raw)
    except (ValueError, TypeError):
        raise ValueError("工作区来源配置不是有效 JSON。") from None
    if (not isinstance(roots, dict) or not roots
            or any(not isinstance(k, str) or not isinstance(v, str) for k, v in roots.items())):
        raise ValueError("工作区来源必须是名称到本机目录的映射。")
    return roots


def _validate_storage(root: Path, sources) -> Path:
    root = root.expanduser().resolve()
    for source in sources.roots.values():
        if root == source or root.is_relative_to(source) or source.is_relative_to(root):
            raise ValueError("工作区存储与原项目来源目录必须分开。")
    return root


@lru_cache(maxsize=4)
def _runtime(root: str, sources_json: str) -> WorkspaceRuntime:
    from .lab_project_sources import ProjectSourceRegistry
    from .lab_workspace_store import WorkspaceStore
    from .lab_workspace_runner import WorkspaceRunner

    sources = ProjectSourceRegistry(_source_roots(sources_json))
    storage = _validate_storage(Path(root), sources)
    store = WorkspaceStore(storage, sources)
    return WorkspaceRuntime(store, WorkspaceRunner(store))


@lru_cache(maxsize=4)
def _remote_runtime(config_path: str, modified: int, size: int):
    from .lab_workspace_transport import load_remote_runtime
    return load_remote_runtime(config_path)


def get_workspace_runtime():
    config = os.environ.get(REMOTE_ENV, "").strip()
    if config:
        try:
            info = Path(config).stat()
        except OSError:
            raise ValueError("本机运行器连接配置不可用，请检查工作区连接。") from None
        return _remote_runtime(config, info.st_mtime_ns, info.st_size)
    if not workspace_enabled():
        raise ValueError("本机代码工作区尚未配置，或当前为托管只读服务。")
    return _runtime(os.environ[ROOT_ENV], os.environ.get(SOURCES_ENV, ""))


def build_workspace_command(*, port: int = 8633) -> list[str]:
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("工作区端口必须为 1024 到 65535 的整数。")
    script = Path(__file__).with_name("lab_workspace_ui.py")
    return [sys.executable, "-m", "streamlit", "run", str(script),
            "--server.address", "127.0.0.1", "--server.port", str(port),
            "--server.headless", "true", "--browser.gatherUsageStats", "false",
            "--theme.base", "dark", "--theme.backgroundColor", "#11151d",
            "--theme.secondaryBackgroundColor", "#191f2a",
            "--theme.textColor", "#dce3ef", "--theme.primaryColor", "#a5baff"]


def launch_environment(storage: str | Path, roots: Mapping[str, str] | None = None,
                       *, environ: Mapping[str, str] | None = None) -> dict[str, str]:
    from .lab_project_sources import ProjectSourceRegistry

    sources = ProjectSourceRegistry(roots)
    selected = _validate_storage(Path(storage), sources)
    env = dict(os.environ if environ is None else environ)
    for name in _CLIENT_CONFIGS:
        env.pop(name, None)
    env.update({ROOT_ENV: str(selected),
                SOURCES_ENV: json.dumps({k: str(v) for k, v in sources.roots.items()}),
                "NSGABLACK_CATALOG_HOSTED": "0",
                "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false"})
    return env


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="打开本机 Project 代码与实验工作区")
    parser.add_argument("--storage", type=Path,
                        default=Path.home() / ".nsgablack" / "project-workspaces",
                        help="修订、数据快照与运行历史的独立存储目录")
    parser.add_argument("--project-root", action="append", default=[], metavar="NAME=PATH",
                        help="登记可信 Project 来源；可重复。不指定时使用框架 examples/cases")
    parser.add_argument("--port", type=int, default=8633)
    args = parser.parse_args(argv)
    roots = {}
    for value in args.project_root:
        name, separator, path = value.partition("=")
        if not separator or not name or not path or name in roots:
            parser.error("--project-root 使用唯一的 NAME=PATH 格式。")
        roots[name] = path
    try:
        env = launch_environment(args.storage, roots or None)
        command = build_workspace_command(port=args.port)
    except ValueError as exc:
        parser.error(str(exc))
    return subprocess.call(command, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
