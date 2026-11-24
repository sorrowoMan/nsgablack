"""Install the shared foundations into Codex's native startup guidance.

The managed section is a versioned copy, not a second knowledge authority.
No model call, Project import, permission change, or MCP execution is involved.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from .lab_knowledge import read_framework_basics

START = "<!-- black-framework-foundations:start -->"
END = "<!-- black-framework-foundations:end -->"
MIN_BUDGET = 98304


def managed_section():
    basics = read_framework_basics()
    metadata = {**basics["metadata"], "source_root": str(Path(__file__).resolve().parents[1])}
    return (START + "\n<!-- " + json.dumps(metadata, ensure_ascii=False) + " -->\n"
        "## Black Framework 适用范围\n\n"
        "以下基础仅在讨论或开发 blackbase、nsgablack、mlblack 及其 Project 时应用；"
        "其他任务遵循各自工程规则。本段不增加执行、资源或发布权限，具体工程规则仍优先。\n\n"
        + basics["content"] + "\n\n## 当前工程和真实接口\n\n"
        "讨论基本概念时直接使用以上知识，不必先扫描整库。涉及实际工程时，"
        "使用 black-framework MCP 的 framework_context 核对实际源码根与基础版本；"
        "以 list_projects/open_project 读取目标 Project 的保存设计与装配状态，"
        "按用户指定或当前工作目录定位工程，不让用户重新介绍已保存的内容。"
        "源码根或版本不一致时明确说明，不能把另一工作树的查询当作当前实现。"
        "具体调用再用 framework_api 查当前签名，缺少工具时定向读局部源码。"
        "按想法选择普通函数、Pool操作、Unit扩展或Adapter，不因新算法就重写基础设施。"
        "保持同一个AI完成查证、编码、测试与修复；测试标准和通过收据须对应当前源码。\n\n"
        "本段由 nsgablack.catalog.codex_bootstrap 从共用 FOUNDATIONS.md 生成。"
        "更新后用 --check 检查，显式 --install 同步；不要把这份安装副本当作独立语义源。\n"
        + END + "\n")


def _replace_section(raw):
    text = raw.decode("utf-8-sig")
    if text.count(START) != text.count(END) or text.count(START) > 1:
        raise ValueError("bootstrap_markers_invalid")
    section = managed_section().encode("utf-8")
    if START not in text:
        return raw + (b"\n\n" if raw and not raw.endswith(b"\n\n") else b"") + section
    begin = raw.index(START.encode())
    end = raw.index(END.encode(), begin) + len(END.encode())
    if end < len(raw) and raw[end:end+2] == b"\r\n":
        end += 2
    elif raw[end:end+1] == b"\n":
        end += 1
    return raw[:begin] + section + raw[end:]


def _config(raw):
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    return tomllib.loads(raw.decode("utf-8-sig"))


def _budget_config(raw):
    parsed = _config(raw)
    budget = parsed.get("project_doc_max_bytes", 32768)
    if type(budget) is not int or budget < 1:
        raise ValueError("bootstrap_budget_invalid")
    if budget >= MIN_BUDGET:
        return raw
    # Match complete TOML scalars (including 32_768/+32768/0x8000), then
    # verify the parsed document. A nested key or text inside a string cannot
    # accidentally be accepted as the root setting.
    text = raw.decode("utf-8-sig")
    expected = {**parsed, "project_doc_max_bytes": MIN_BUDGET}
    if "project_doc_max_bytes" in parsed:
        pattern = r'''(?m)^([ \t]*(?:project_doc_max_bytes|"project_doc_max_bytes"|'project_doc_max_bytes')[ \t]*=[ \t]*)([^#\r\n]+)'''
        changed = None
        for match in re.finditer(pattern, text):
            value = match[2]
            trailing = value[len(value.rstrip()):]
            trial = text[:match.start(2)] + str(MIN_BUDGET) + trailing + text[match.end(2):]
            try:
                correct_target = _config(trial.encode()) == expected
            except ValueError:
                # A matching line may be text inside a multiline string.
                continue
            if correct_target:
                changed = trial
                break
        if changed is None:
            raise ValueError("bootstrap_budget_layout_unsupported")
    else:
        changed = "project_doc_max_bytes = " + str(MIN_BUDGET) + "\n" + text
    result = (b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + changed.encode("utf-8")
    after = _config(result)
    if after != expected:
        raise ValueError("bootstrap_unrelated_config_changed")
    return result


def _array_end(text, start):
    """Find a TOML array boundary without treating quoted/comment ] as syntax."""
    i, depth, quote, comment, last = start, 0, None, False, None
    while i < len(text):
        c = text[i]
        if comment:
            comment = c != "\n"
        elif quote:
            if quote.startswith('"') and c == "\\":
                i += 2
                continue
            if text.startswith(quote, i):
                i += len(quote)
                quote, last = None, "string"
                continue
        elif c == "#":
            comment = True
        elif c in "\"'":
            quote = c * 3 if text.startswith(c * 3, i) else c
            i += len(quote)
            continue
        elif c == "[":
            depth += 1
            last = c
        elif c == "]":
            depth -= 1
            if depth == 0:
                return i + 1, last
        elif not c.isspace():
            last = c
        i += 1
    raise ValueError("bootstrap_mcp_array_unclosed")


def _current_project_config(raw):
    """Opt the already registered framework server into host-cwd discovery."""
    parsed = _config(raw)
    server = parsed.get("mcp_servers", {}).get("black-framework")
    if server is None:
        return raw
    args = server.get("args", [])
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise ValueError("bootstrap_mcp_arguments_invalid")
    if "--include-current-project" in args:
        return raw
    if not any(args[i:i+2] == ["-m", "nsgablack.catalog.mcp_server"] for i in range(len(args)-1)):
        raise ValueError("bootstrap_framework_mcp_command_not_recognized")
    text = raw.decode("utf-8-sig")
    table = re.search(r'(?ms)^\[mcp_servers\.(?:black-framework|"black-framework")\][^\n]*\n(.*?)(?=^\[|\Z)', text)
    if table is None:
        raise ValueError("bootstrap_mcp_layout_unsupported")
    argument = re.compile(r'(?m)^[ \t]*args[ \t]*=[ \t]*\[').search(text, table.start(1))
    if argument is None:
        raise ValueError("bootstrap_mcp_argument_layout_unsupported")
    end, last = _array_end(text, argument.end()-1)
    extra = ("," if args and last != "," else "") + ' "--include-current-project"'
    # Insert before the closing bracket, preserving existing items/comments.
    changed = text[:end-1] + extra + text[end-1:]
    result = (b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + changed.encode("utf-8")
    expected = _config(raw)
    expected["mcp_servers"]["black-framework"]["args"] = [*args, "--include-current-project"]
    if _config(result) != expected:
        raise ValueError("bootstrap_unrelated_mcp_config_changed")
    return result


def _atomic(path, expected, replacement):
    if (path.read_bytes() if path.exists() else b"") != expected:
        raise ValueError("bootstrap_target_changed_during_install")
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".framework-guidance-", delete=False) as file:
        temp = Path(file.name)
        file.write(replacement)
    try:
        if (path.read_bytes() if path.exists() else b"") != expected:
            raise ValueError("bootstrap_target_changed_during_install")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def bootstrap(codex_home, *, install=False):
    home = Path(codex_home).resolve()
    agents, config = home / "AGENTS.md", home / "config.toml"
    override = home / "AGENTS.override.md"
    if override.exists() and override.read_bytes().strip():
        raise ValueError("nonempty_global_override_shadows_bootstrap")
    old_agents = agents.read_bytes() if agents.exists() else b""
    old_config = config.read_bytes() if config.exists() else b""
    new_agents, new_config = _replace_section(old_agents), _current_project_config(_budget_config(old_config))
    changed = new_agents != old_agents or new_config != old_config
    backup = None
    if install and changed:
        home.mkdir(parents=True, exist_ok=True)
        backup = home / "private/framework-bootstrap-backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup.mkdir(parents=True, exist_ok=False)
        if os.name == "nt":
            actor = subprocess.check_output(["whoami"], text=True).strip()
            subprocess.run(["icacls.exe", str(backup), "/inheritance:r", "/grant:r", actor + ":(OI)(CI)(F)"],
                           check=True, capture_output=True, timeout=30)
        else:
            backup.chmod(0o700)
        (backup / "AGENTS.md").write_bytes(old_agents)
        (backup / "config.toml").write_bytes(old_config)
        _atomic(config, old_config, new_config)
        try:
            _atomic(agents, old_agents, new_agents)
        except Exception:
            _atomic(config, new_config, old_config)
            raise
    return {"status": "installed" if install and changed else "stale" if changed else "current",
            "agents_path": str(agents), "config_path": str(config), "backup_path": str(backup) if backup else None,
            "framework_basics": read_framework_basics()["metadata"],
            "managed_section_sha256": hashlib.sha256(managed_section().encode()).hexdigest(),
            "project_doc_max_bytes": _config(new_config if install else old_config).get("project_doc_max_bytes", 32768),
            "required_project_doc_max_bytes": MIN_BUDGET,
            "current_project_opt_in": "--include-current-project" in _config(new_config if install else old_config).get("mcp_servers", {}).get("black-framework", {}).get("args", []),
            "unrelated_configuration_preserved": True, "model_call": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="同步日常Codex框架基础指导；默认只检查")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME", Path.home()/".codex")))
    args = parser.parse_args(argv)
    if args.check and args.install:
        parser.error("--check与--install不能同时使用")
    result = bootstrap(args.codex_home, install=args.install)
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result["status"] == "stale" else 0


if __name__ == "__main__":
    raise SystemExit(main())
