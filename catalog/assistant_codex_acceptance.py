"""Developer-only Codex + native MCP acceptance using existing fixed oracles.

No model SDK, API credential, second algorithm author, or new execution kernel.
The child Codex owns all corrected/generated component source. The host selects
the frozen task, formal Project and validator, and may inject a declared initial
fault seed; it never writes the repaired implementation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tempfile


def _binding(idea_id, validation_profile="baseline"):
    if idea_id == "deadband_blend_change":
        from .assistant_startup_acceptance import execute_candidate, spec_identity
        from .assistant_novel_acceptance import TARGET
        if validation_profile not in ("baseline", "startup-deadband-v1"):
            raise ValueError("startup_task_profile_invalid")
        return {"edit_validator": execute_candidate, "validation_identity": spec_identity(),
                "edit_call_contracts": {TARGET: {"deadband_blend_change.request": "nsgablack.adapters.change.ChangeRequest"}}}
    from .assistant_novel_acceptance import IDEAS, _contracts, execute_candidate, spec_identity
    if validation_profile == "archive-distance-v2":
        from .assistant_archive_distance_acceptance import IDEA, execute_candidate, spec_identity
        if idea_id != IDEA:
            raise ValueError("archive_distance_profile_requires_archive_task")
    elif validation_profile != "baseline":
        raise ValueError("unknown_validation_profile")
    idea = next(idea for idea in IDEAS if idea["id"] == idea_id)
    return {"edit_validator": lambda proposal: execute_candidate(proposal, idea_id),
            "validation_identity": spec_identity(), "edit_call_contracts": _contracts(idea)}


def reflection_validation():
    return _binding("center_reflection_expansion")


def archive_validation():
    return _binding("archive_maximin_survivor")


def archive_distance_validation():
    return _binding("archive_maximin_survivor", "archive-distance-v2")


def age_validation():
    return _binding("age_population_unit")


def startup_validation():
    return _binding("deadband_blend_change", "startup-deadband-v1")


FACTORIES = {"center_reflection_expansion": "reflection_validation",
             "archive_maximin_survivor": "archive_validation", "age_population_unit": "age_validation",
             "deadband_blend_change": "startup_validation"}


def _environment(use_windows_proxy=False):
    names = ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "USERPROFILE",
             "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH", "USERNAME", "USERDOMAIN",
             "PROGRAMFILES", "PROGRAMFILES(X86)", "PROCESSOR_ARCHITECTURE", "OS", "CODEX_HOME")
    env = {name: os.environ[name] for name in names if name in os.environ}
    env["PYTHONIOENCODING"] = "utf-8"
    if use_windows_proxy:
        if sys.platform != "win32":
            raise ValueError("existing_windows_proxy_requires_windows")
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as key:
            if not winreg.QueryValueEx(key, "ProxyEnable")[0]:
                raise ValueError("existing_windows_proxy_not_enabled")
            proxy = winreg.QueryValueEx(key, "ProxyServer")[0]
        if "=" in proxy:
            settings = dict(part.split("=", 1) for part in proxy.split(";") if "=" in part)
            proxy = settings.get("https", settings.get("http", ""))
        if not proxy:
            raise ValueError("existing_windows_proxy_missing")
        if "://" not in proxy:
            proxy = "http://" + proxy
        env.update(HTTPS_PROXY=proxy, HTTP_PROXY=proxy)
    else:
        for name in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NO_PROXY"):
            if name in os.environ:
                env[name] = os.environ[name]
    return env


def _redact(value):
    return re.sub(r"sk-(?:proj-)?[A-Za-z0-9_-]{24,}", "<redacted-key>", value)


def _share_with_invoking_user(project):
    """Keep sandbox-created files readable by the owner of this fresh copy.

    OWNER RIGHTS alone follows the new file's sandbox account. Explicitly
    retain the invoking user's access on each existing parent directory before
    Codex creates files; do not grant Everyone or change any source checkout.
    """
    if sys.platform != "win32":
        return {"changed": False, "reason": "not_windows"}
    actor = subprocess.check_output(["whoami"], text=True).strip()
    if not actor or "\n" in actor:
        raise ValueError("invoking_user_unavailable")
    result = subprocess.run(["icacls.exe", str(project), "/grant", actor + ":(OI)(CI)(M)", "/T", "/C"],
                            capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError("temporary_project_owner_access_failed")
    return {"changed": True, "principal": "invoking_user", "scope": "only_fresh_temporary_project"}


def _user_config():
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    path = home / "config.toml"
    return tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _resolve_codex(explicit=None):
    if explicit is not None:
        path = Path(explicit)
        if not path.is_file():
            raise ValueError("codex_executable_unavailable")
        return path
    if sys.platform == "win32":
        import psutil
        for process in psutil.process_iter(["name", "exe"]):
            try:
                exe = process.info.get("exe") or ""
                if (process.info.get("name", "").lower() == "codex.exe"
                        and exe.replace("\\", "/").lower().endswith("/app/resources/codex.exe")
                        and Path(exe).is_file()):
                    return Path(exe)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    command = shutil.which("codex.cmd" if sys.platform == "win32" else "codex")
    if not command:
        raise ValueError("codex_executable_unavailable")
    return Path(command)


def _disable_other_servers():
    config = _user_config()
    args = []
    for name in config.get("mcp_servers", {}):
        if name == "black-framework":
            continue
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", name):
            raise ValueError("mcp_server_name_requires_explicit_isolation")
        args.extend(["-c", "mcp_servers." + name + ".enabled=false"])
    for plugin in config.get("plugins", {}):
        args.extend(["-c", "plugins." + json.dumps(plugin) + ".enabled=false"])
    return args


def _stop(process):
    import psutil
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
    except psutil.NoSuchProcess:
        return
    for child in reversed(children):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    try:
        parent.kill()
    except psutil.NoSuchProcess:
        pass


def review_acceptance(output):
    """Bind the last real MCP receipt to the file actually written by Codex."""
    from .assistant_novel_acceptance import TARGET
    output = Path(output)
    report_bytes = (output / "report.json").read_bytes()
    report = json.loads(report_bytes)
    checks, deliveries, threads, writes = [], [], set(), 0
    for line in (output / "events.jsonl").read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("type") == "thread.started":
            threads.add(event["thread_id"])
        if event.get("type") != "item.completed":
            continue
        item = event.get("item", {})
        if item.get("type") in {"file_change", "command_execution"} and item.get("status") == "completed":
            writes += 1
        if item.get("type") != "mcp_tool_call" or item.get("server") != "black-framework":
            continue
        data = (item.get("result") or {}).get("structured_content")
        if not isinstance(data, dict):
            continue
        if item.get("tool") == "check_project_edit" and data.get("path") == TARGET:
            checks.append(data)
        if item.get("tool") == "edit_result" and data.get("result", {}).get("path") == TARGET:
            deliveries.append(data)
    last = checks[-1] if checks else {}
    delivery = deliveries[-1] if deliveries else {}
    validation = last.get("validation", {})
    expected = last.get("code_sha256")
    project = Path(report["project"]).resolve()
    target = project / TARGET
    file_error = None
    try:
        actual = (hashlib.sha256(target.read_bytes()).hexdigest()
                  if target.is_file() and not target.is_symlink()
                  and target.resolve().is_relative_to(project) and target.stat().st_size <= 131072 else None)
    except OSError as error:
        actual, file_error = None, type(error).__name__
    readback_path = output / "post-write-mcp.json"
    readback = json.loads(readback_path.read_text(encoding="utf-8")) if readback_path.exists() else {}
    read_source = readback.get("read_receipt", {}).get("source", {})
    native_read = (readback.get("native_stdio_MCP") is True
                   and readback.get("project_read_succeeded") is True
                   and read_source.get("sha256") == actual and read_source.get("path") == TARGET
                   and read_source.get("project_id") == report.get("project_id"))
    passed = (report.get("exit_code") == 0 and report.get("stop_reason") is None
        and last.get("check", {}).get("status") != "rejected"
        and validation.get("status") == "passed" and validation.get("executed") is True
        and expected is not None and expected == actual == validation.get("code_sha256")
        == validation.get("executed_source_sha256")
        and validation.get("validation_identity") == report["validation_identity"]
        and delivery.get("verification_status") == "passed"
        and delivery.get("result", {}).get("edit_digest") == last.get("edit_digest")
        and len(threads) == 1 and (not report.get("resume_thread") or threads == {report["resume_thread"]})
        and writes > 0 and native_read)
    result = {"schema": "nsgablack.codex_mcp_delivery_review/v1", "status": "passed" if passed else "not_delivered",
        "report_sha256": hashlib.sha256(report_bytes).hexdigest(), "idea": report["idea"],
        "thread_ids": sorted(threads), "resume_thread": report.get("resume_thread"),
        "actual_file": str(target), "actual_file_sha256": actual, "file_error": file_error,
        "native_mcp_readback_verified": native_read,
        "validated_code_sha256": expected,
        "edit_digest": last.get("edit_digest"), "verification_status": delivery.get("verification_status"),
        "validation": validation, "host_algorithm_source_written": bool(report.get("seed_code_sha256")),
        "host_corrected_source_written": False,
        "attempts": [{"code_sha256": row.get("code_sha256"), "check": row.get("check", {}).get("status"),
            "validation": row.get("validation", {}).get("status")} for row in checks]}
    (output / "review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def _post_write_readback(output, report):
    import anyio
    from mcp import Client, StdioServerParameters
    from .assistant_novel_acceptance import TARGET
    async def read():
        args = ["-I", "-m", "nsgablack.catalog.mcp_server", "--expected-framework-root",
                str(Path(__file__).resolve().parents[1]), "--project-root",
                "acceptance=" + str(Path(report["project"]).parent)]
        async with Client(StdioServerParameters(command=sys.executable, args=args), read_timeout_seconds=40) as client:
            opened = await client.call_tool("open_project", {"project_id": report["project_id"]})
            if opened.is_error:
                raise ValueError("project_reopen_failed")
            actual = await client.call_tool("project_read", {"session_id": opened.structured_content["session_id"],
                "path": TARGET, "start_line": 1, "max_lines": 1})
            if actual.is_error:
                raise ValueError("project_readback_failed")
            receipt = {key: value for key, value in actual.structured_content.items() if key != "excerpt"}
            return {"native_stdio_MCP": True, "model_inference_calls": 0,
                    "open_project_succeeded": True, "project_read_succeeded": True,
                    "source_revision": opened.structured_content["project"]["source_digest"],
                    "read_receipt": receipt}
    try:
        proof = anyio.run(read)
    except Exception as error:
        proof = {"native_stdio_MCP": True, "project_read_succeeded": False, "error_type": type(error).__name__}
    (Path(output) / "post-write-mcp.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")


def run_acceptance(*, idea_id, codex, output, model, timeout_seconds=300,
                   max_tool_calls=45, use_windows_proxy=False, resume_thread=None, seed_source=None,
                   validation_profile="current", native_startup_only=False):
    from .assistant_novel_acceptance import IDEAS, INITIALIZATION_CONTRACT, POLICY
    from .lab_knowledge import read_framework_basics, framework_system_prompt
    from .assistant_session_acceptance import create_teaching_project
    from .lab_jobs import spec_digest
    from .mcp_server import FrameworkWorkspace
    if validation_profile == "current":
        validation_profile = ("archive-distance-v2" if idea_id == "archive_maximin_survivor" else
                              "startup-deadband-v1" if idea_id == "deadband_blend_change" else "baseline")
    binding = _binding(idea_id, validation_profile)
    factory = "archive_distance_validation" if validation_profile == "archive-distance-v2" else FACTORIES[idea_id]
    login = subprocess.run([str(codex), "login", "status"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=_environment(use_windows_proxy), timeout=15)
    if (login.returncode or "Logged in using ChatGPT" not in login.stdout + login.stderr
            or _user_config().get("model_provider") not in (None, "openai")):
        raise ValueError("codex_chatgpt_login_required_no_api_fallback")
    if idea_id == "deadband_blend_change":
        from .assistant_startup_acceptance import TASK as idea
    else:
        idea = next(row for row in IDEAS if row["id"] == idea_id)
    native_bootstrap = None
    if native_startup_only:
        from .codex_bootstrap import bootstrap
        native_bootstrap = bootstrap(Path(os.environ.get("CODEX_HOME", Path.home()/".codex")))
        if native_bootstrap["status"] != "current":
            raise ValueError("native_guidance_missing_or_stale")
    output = Path(output).resolve()
    # A previous run, including a failed one, is never silently overwritten.
    output.mkdir(parents=True, exist_ok=False)
    # Git/pytest private cache ACLs may block the Windows sandbox's inherited
    # write capability. Give Codex one independent, explicitly writable formal
    # Project instead of broadening permissions on the source repository.
    workspace = Path(tempfile.mkdtemp(prefix="black-framework-codex-"))
    sources, project_id = create_teaching_project(workspace)
    project = sources.resolve_project(project_id)
    seed_sha = None
    if seed_source is not None:
        from .assistant_novel_acceptance import TARGET
        if not isinstance(seed_source, str) or len(seed_source.encode("utf-8")) > 131072:
            raise ValueError("invalid_math_repair_seed")
        seed_sha = hashlib.sha256(seed_source.encode("utf-8")).hexdigest()
        # Only this initial, explicitly declared fault injection is host-written.
        # All corrected source must subsequently come from the tested Codex.
        (project / TARGET).write_bytes(seed_source.encode("utf-8"))
        (output / "initial-seed.py").write_bytes(seed_source.encode("utf-8"))
    owner_access = _share_with_invoking_user(project)
    source = FrameworkWorkspace(sources).context()["framework_source"]
    root = Path(__file__).resolve().parents[1]
    args = [str(codex), "exec", "-c", "approval_policy=\"never\"",
        *([] if native_startup_only else ["-c", "project_doc_max_bytes=98304"]),
        *_disable_other_servers(),
        "-c", "mcp_servers.black-framework.default_tools_approval_mode=\"approve\"",
        "-c", "model=" + json.dumps(model),
        "-c", "mcp_servers.black-framework.command=" + json.dumps(sys.executable),
        "-c", "mcp_servers.black-framework.args=" + json.dumps([
            "-m", "nsgablack.catalog.mcp_server", "--expected-framework-root", str(root),
            "--project-root", "acceptance=" + str(workspace), "--validation-factory",
            "nsgablack.catalog.assistant_codex_acceptance:" + factory]),
        "-c", "mcp_servers.black-framework.tool_timeout_sec=100",
        "--sandbox", "workspace-write", "--add-dir", str(project), "-C", str(project)]
    if resume_thread is not None:
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", resume_thread):
            raise ValueError("invalid_codex_resume_thread")
        args.extend(["resume", resume_thread])
    args.extend(["--skip-git-repo-check", "--json", "-o", str(output / "final.txt"), "-"])
    prompt = ("用户已明确授权本次隔离工程的组件实现和测试。你是本任务唯一的算法代码作者；"
        "不得调用或委托其他AI。直接从以下算法想法开始工作，按已安装Skill使用原生black-framework MCP。"
        "先framework_context核对源码，再list_projects/open_project读取保存状态，查真实接口后"
        "提交完整源码到check_project_edit。该工具由宿主预先绑定真实隔离验证器，按失败自行修复，"
        "必须用edit_result核对本文件最后一次通过。工作日志已由宿主统一记录，"
        "本轮只使用black-framework的MCP和本地编辑/终端工具，不调用其他业务插件。"
        "原工程在交付前保持不变，禁止读取凭据、"
        "历史模型代码、测试参考实现及assistant_*acceptance验证器源码；不要修改测试或验收条件。"
        "本次Project身份：" + project_id + "；实际写入根目录：" + project.as_posix()
        + "。不要写入其他旧工作目录。\n算法要求：" + idea["instruction"]
        + "\n" + INITIALIZATION_CONTRACT + "\n执行约束：" + POLICY
        + "\n通过后将你自己刚通过的同一份源码写入本Project对应path，最后报告path、"
        "code_sha256、edit_digest、validation_identity及实际结果；明确原工程已应用但正式提交未做。"
        "若预算内无法通过，如实说明。最多" + str(max_tool_calls) + "次工具调用，避免泛查。")
    if resume_thread:
        prompt = ("这是同一Codex会话的开发续验；原有结果仍保留。现在使用独立TEMP正式Project，"
                  "以本轮宿主绑定的验证身份为准，不能把旧通过当作本轮通过。"
                  "重新打开MCP工程，在本轮指定源码上独立验证和修复，再由你自己写入本次根目录。\n" + prompt)
    if seed_sha:
        prompt = ("本轮是明确标记的数学故障修复验收，当前Project已有待修复实现。"
            "它是本次任务允许读取的现有源码，不属于禁止查阅的其他历史正确实现。"
            "先用project_read读取cases/hybrid_search/adapter/novel_ops.py，"
            "必须将该文件原样（SHA256=" + seed_sha + "）提交check_project_edit，"
            "实际看到数学测试失败后，才开始诊断和修改。不要先修好再补做失败演示。"
            "之后由你在同一会话内自行看错误、改代码、重验直至通过并落盘；"
            "不允许弱化断言、跳过测试、修改Problem或验收器，也不能调用别的AI。"
            "宿主不提供故障位置、正确代码或修复建议。\n" + prompt)
    basics = read_framework_basics()
    if not native_startup_only:
        prompt = framework_system_prompt(prompt, basics=basics)
    (output / "prompt.txt").write_text(prompt, encoding="utf-8")
    report = {"schema": "nsgablack.codex_mcp_acceptance/v1", "idea": idea_id,
        "created_at": datetime.now(timezone.utc).isoformat(), "status": "running",
        "model_configured": model, "model_identity_attested": False,
        "codex_executable": str(codex), "login_check": "ChatGPT_subscription_login_confirmed",
        "framework_source": source, "validation_identity": binding["validation_identity"],
        "validation_profile": validation_profile, "framework_basics": basics["metadata"],
        "foundations_loaded_before_model_start": not native_startup_only,
        "foundations_loading_mode": "native_global_agents" if native_startup_only else "task_prompt",
        "native_bootstrap_check": native_bootstrap,
        "project_id": project_id, "project": str(project), "resume_thread": resume_thread,
        "owner_access": owner_access,
        "prompt_sha256": spec_digest({"prompt": prompt}),
        "timeout_seconds": timeout_seconds, "max_tool_calls": max_tool_calls,
        "network_configuration": "existing_windows_user_proxy" if use_windows_proxy else "inherited_proxy_env",
        "api_key_used": False, "algorithm_source_written_by_host": bool(seed_sha),
        "seed_code_sha256": seed_sha, "host_source_actions": "initial_fault_seed_only" if seed_sha else "none",
        "corrected_source_written_by_host": False,
        "limitations": ["Codex task acceptance, not a proof of permanent model internalization.",
                        "Previously frozen mathematical tasks; not newly designed blind algorithms.",
                        "Representative source fingerprints are not a full-tree lock."]}
    report_path = output / "report.json"
    def save():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save()
    process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", cwd=project,
        env=_environment(use_windows_proxy), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    messages = queue.Queue()
    def read(stream, name):
        for line in stream:
            messages.put((name, _redact(line)))
        messages.put((name, None))
    for stream, name in ((process.stdout, "stdout"), (process.stderr, "stderr")):
        threading.Thread(target=read, args=(stream, name), daemon=True).start()
    process.stdin.write(prompt)
    process.stdin.close()
    start, completed, tool_calls = time.monotonic(), set(), 0
    events, stop_reason = [], None
    with (output / "events.jsonl").open("w", encoding="utf-8") as log, (output / "stderr.txt").open("w", encoding="utf-8") as err:
        while len(completed) < 2:
            if stop_reason is None and (time.monotonic() - start > timeout_seconds or tool_calls > max_tool_calls):
                stop_reason = "wall_clock_limit" if time.monotonic() - start > timeout_seconds else "tool_call_limit"
                _stop(process)
            try:
                name, line = messages.get(timeout=.2)
            except queue.Empty:
                continue
            if line is None:
                completed.add(name)
                continue
            if name == "stderr":
                err.write(line)
                err.flush()
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            item = event.get("item", {})
            if item.get("type") == "reasoning":
                continue
            log.write(json.dumps(event, ensure_ascii=False) + "\n")
            log.flush()
            events.append(event)
            if event.get("type") == "item.started" and item.get("type") in {"mcp_tool_call", "command_execution", "file_change"}:
                tool_calls += 1
    report.update(exit_code=process.wait(), elapsed_seconds=round(time.monotonic()-start, 2),
                  tool_calls=tool_calls, stop_reason=stop_reason)
    report["thread_id"] = next((e["thread_id"] for e in events if e.get("type") == "thread.started"), None)
    report["status"] = "stopped" if stop_reason else "client_completed" if report["exit_code"] == 0 else "client_failed"
    # Client completion alone does not constitute component acceptance.
    report["component_acceptance"] = "requires_source_and_receipt_review"
    save()
    _post_write_readback(output, report)
    reviewed = review_acceptance(output)
    return {**report, "component_acceptance": reviewed["status"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description="开发端Codex+原生MCP验收；只在显式--run后调用Codex")
    parser.add_argument("--run", choices=tuple(FACTORIES))
    parser.add_argument("--codex", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--model", help="默认使用用户Codex配置中的模型，不自动更换")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--existing-windows-proxy", action="store_true")
    parser.add_argument("--resume-thread", help="仅续验原来的Codex会话；保留先前失败记录")
    parser.add_argument("--seed-source", type=Path, help="开发端显式提供的初始待修复源码；不改变固定验收")
    parser.add_argument("--validation-profile", choices=("current", "baseline", "archive-distance-v2", "startup-deadband-v1"), default="current",
                        help="默认档案任务使用增强标准；baseline仅用于明确重放旧验收")
    parser.add_argument("--native-startup-only", action="store_true", help="仅靠日常全局AGENTS提供基础，不在任务提示重复注入")
    args = parser.parse_args(argv)
    if not args.run:
        print(json.dumps({"ideas": list(FACTORIES), "model_started": False}))
        return 0
    if not args.output or not 30 <= args.timeout_seconds <= 900:
        parser.error("--run需要全新--output及30到900秒的时限")
    try:
        executable = _resolve_codex(args.codex)
    except ValueError:
        parser.error("找不到可用Codex客户端；可通过--codex显式指定")
    model = args.model or _user_config().get("model")
    if not isinstance(model, str) or not model:
        parser.error("用户配置没有默认模型；请显式指定--model")
    report = run_acceptance(idea_id=args.run, codex=executable, output=args.output,
        model=model, timeout_seconds=args.timeout_seconds, use_windows_proxy=args.existing_windows_proxy,
        resume_thread=args.resume_thread,
        seed_source=args.seed_source.read_text(encoding="utf-8") if args.seed_source else None,
        validation_profile=args.validation_profile, native_startup_only=args.native_startup_only)
    print(json.dumps({k: report[k] for k in ("status", "thread_id", "elapsed_seconds", "component_acceptance")}))
    return 0 if report["component_acceptance"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
