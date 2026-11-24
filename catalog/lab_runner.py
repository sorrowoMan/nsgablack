"""Bounded, declarative trials through the genuine Project/Case runtime.

This module is a private runner surface, never a Catalog database capability.
Inputs contain a checked assembly and Problem definition, not arbitrary code,
paths or commands. Mathematical expressions use the same bounded interpreter
as the exported Problem.
Each trial exports the same Project that the user downloads, then starts its
ordinary CLI in a fresh directory with an explicit, credential-free environment.
"""
from __future__ import annotations

from collections import deque
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Mapping
from uuid import uuid4


RESULT_SCHEMA = "nsgablack.lab.trial/v1"
MAX_LOG_BYTES = 48 * 1024
MAX_JSON_BYTES = 4 * 1024 * 1024


class TrialError(ValueError):
    """A public diagnostic with no interpolated host paths or environment."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        raise TrialError("receipt_missing", "正式运行收据缺失或超过大小限制。")

    def no_constant(_value):
        raise ValueError("nonfinite JSON")

    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON field")
            value[key] = item
        return value

    try:
        value = json.loads(path.read_text(encoding="utf-8"),
                           parse_constant=no_constant, object_pairs_hook=unique_pairs)
    except (ValueError, UnicodeError):
        raise TrialError("receipt_invalid", "正式运行收据不是有效的有限 JSON 对象。") from None
    if not isinstance(value, dict):
        raise TrialError("receipt_invalid", "正式运行收据必须是 JSON 对象。")
    return value


def _trial_environment(temporary: Path) -> dict[str, str]:
    """Allow OS startup values, not service config, credentials or grants."""
    # Python/OS libraries may need PATH and Windows system directories. Package
    # roots come from the running trusted installation, never inherited PYTHONPATH.
    allowed = ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "LANG", "LC_ALL", "TZ")
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    roots = []
    for name in ("nsgablack", "blackbase"):
        module = importlib.util.find_spec(name)
        if module is None or not module.submodule_search_locations:
            raise TrialError("runtime_unavailable", "实验台需要可导入的 nsgablack 与 blackbase 安装。")
        roots.extend(str(Path(location).resolve().parent) for location in module.submodule_search_locations)
    env.update({
        "PYTHONPATH": os.pathsep.join(dict.fromkeys(roots)),
        "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1",
        "PYTHONUNBUFFERED": "1", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1", "TEMP": str(temporary),
        "TMP": str(temporary), "TMPDIR": str(temporary), "HOME": str(temporary),
        "USERPROFILE": str(temporary), "XDG_CONFIG_HOME": str(temporary / "config"),
        "XDG_CACHE_HOME": str(temporary / "cache"),
    })
    return env


class _TailLog:
    """Consume the pipe continuously while retaining a bounded suffix."""

    def __init__(self):
        self.parts: deque[bytes] = deque()
        self.size = 0
        self.truncated = False

    def read(self, stream):
        try:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                self.parts.append(chunk)
                self.size += len(chunk)
                while self.size > MAX_LOG_BYTES and self.parts:
                    first = self.parts.popleft()
                    excess = self.size - MAX_LOG_BYTES
                    self.truncated = True
                    if len(first) > excess:
                        self.parts.appendleft(first[excess:])
                        self.size -= excess
                    else:
                        self.size -= len(first)
        finally:
            stream.close()

    def text(self):
        prefix = "[较早日志已截断]\n" if self.truncated else ""
        return prefix + b"".join(self.parts).decode("utf-8", errors="replace").replace("\r\n", "\n")


class _WindowsJob:
    """Kill descendants even when the Project process has already exited."""

    def __init__(self, process):
        import ctypes
        from ctypes import wintypes

        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                        ("flags", wintypes.DWORD), ("min_working_set", ctypes.c_size_t),
                        ("max_working_set", ctypes.c_size_t), ("active_processes", wintypes.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                        ("scheduling", wintypes.DWORD)]

        class Counters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]

        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", Counters), ("process_memory", ctypes.c_size_t),
                        ("job_memory", ctypes.c_size_t), ("peak_process_memory", ctypes.c_size_t),
                        ("peak_job_memory", ctypes.c_size_t)]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.SetInformationJobObject.restype = wintypes.BOOL
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.TerminateJobObject.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel, self.handle = kernel, kernel.CreateJobObjectW(None, None)
        info = Extended()
        info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.handle or not kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            self.close()
            raise TrialError("process_isolation_failed", "不能建立实验台进程组，已拒绝运行。")
        if not kernel.AssignProcessToJobObject(self.handle, wintypes.HANDLE(int(process._handle))):
            self.close()
            raise TrialError("process_isolation_failed", "不能把运行进程加入隔离组，已拒绝运行。")

    def close(self):
        if self.handle:
            self.kernel.TerminateJobObject(self.handle, 1)
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def _stop_tree(process, job=None):
    if os.name == "nt":
        if job is not None:
            job.close()
        elif process.poll() is None:
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _execute(project: Path, run_id: str, env: dict, timeout: float) -> tuple[int, str, bool]:
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    process = subprocess.Popen([sys.executable, "run_project.py", "--run-id", run_id],
        cwd=project, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, shell=False, **options)
    log = _TailLog()
    reader = threading.Thread(target=log.read, args=(process.stdout,), daemon=True,
                              name="catalog-lab-log")
    job, timed_out = None, False
    try:
        if os.name == "nt":
            job = _WindowsJob(process)
        reader.start()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
    finally:
        _stop_tree(process, job)
        if reader.ident is not None:
            reader.join(timeout=5)
        elif process.stdout:
            process.stdout.close()
    if reader.is_alive():
        raise TrialError("process_cleanup_failed", "运行结束后日志通道未关闭，请检查私有运行器。")
    return process.returncode, log.text(), timed_out


def _count(value, label: str) -> int:
    if type(value) is not int or value < 0:
        raise TrialError("receipt_progress_invalid", f"{label}不是有效的非负整数。")
    return value


def _public_binding(binding: Mapping) -> dict:
    """Preserve actual allocation evidence while omitting private control URIs."""
    allowed = ("workers", "threads", "gpus", "backend", "device", "namespace", "scope",
               "compute_backend", "allocated_threads", "nested")
    result = {key: binding[key] for key in ("schema_version", "status", "method", "current")
              if key in binding}
    for side in ("expected", "effective"):
        context = binding.get(side, {})
        result[side] = {key: context[key] for key in allowed if key in context}
        resources = context.get("resources", {})
        result[side]["resources"] = {key: resources[key] for key in allowed if key in resources}
    return result


def _public_logs(logs: str, temporary: Path) -> str:
    paths = [str(temporary)]
    for name in ("nsgablack", "blackbase"):
        module = importlib.util.find_spec(name)
        paths.extend(str(Path(location).resolve().parent)
                     for location in module.submodule_search_locations or ())
    for index, path in enumerate(paths):
        forms = {path, path.replace("\\", "/")}
        for _ in range(3):
            forms.update(json.dumps(value, ensure_ascii=False)[1:-1] for value in tuple(forms))
        for form in sorted(forms, key=len, reverse=True):
            logs = logs.replace(form, "<trial>" if index == 0 else "<runtime>")
    return logs


def _verify_receipts(project: Path, spec: dict, run_id: str) -> dict:
    from blackbase.project.execution import CaseRunResult
    from blackbase.project.run_manifest import ProjectRunManifest
    from blackbase.wire import thaw_wire_mapping

    manifests = list((project / ".blackbase" / "runs").glob("*/manifest.json"))
    expected_path = project / ".blackbase" / "runs" / run_id / "manifest.json"
    if len(manifests) != 1 or manifests[0] != expected_path:
        raise TrialError("manifest_identity_mismatch", "本次实验必须且只能产生一份对应运行身份的 Project 收据。")
    raw_manifest = _read_json(expected_path)
    try:
        manifest = ProjectRunManifest.from_dict(raw_manifest)
    except (ValueError, TypeError, KeyError):
        raise TrialError("manifest_invalid", "Project 收据不满足正式版本契约。") from None
    if (manifest.run_id != run_id or manifest.framework != "nsgablack"
            or manifest.status != "ok" or manifest.exit_code != 0 or manifest.group != "default"):
        raise TrialError("project_not_successful", "Project 没有交付本次运行的成功收据。")
    if len(manifest.cases) != 1 or manifest.cases[0].get("case_name") != "search":
        raise TrialError("case_set_mismatch", "实验配方必须且只能运行 search Case。")
    row = manifest.cases[0]
    try:
        case = CaseRunResult.from_dict(row["result"])
    except (ValueError, TypeError, KeyError):
        raise TrialError("case_receipt_invalid", "Case 收据不满足正式版本契约。") from None
    if not case.ok or case.status != "succeeded" or row.get("exit_code") != 0:
        raise TrialError("case_not_successful", "search Case 未成功完成。")
    identity = case.identity.as_dict()
    if (identity["project_run_id"] != run_id or identity["root_run_id"] != run_id
            or case.request.case_name != "search" or case.request.project_name != manifest.project_name):
        raise TrialError("case_identity_mismatch", "Case 收据的运行身份与本次 Project 不一致。")
    binding = dict(case.resource_usage.get("binding", {}))
    if binding.get("current") is not True:
        raise TrialError("resource_binding_not_current", "Case 没有确认本次 Project L0 资源授权生效。")
    trace = _read_json(project / "results" / "lab_report.json")
    publication = _verify_report_publication(project, case, trace)
    if trace.get("schema") != "nsgablack.lab.report/v1" or trace.get("spec") != spec:
        raise TrialError("report_spec_mismatch", "实验报告与本次装配配方不一致。")
    if trace.get("project_identity") != identity:
        raise TrialError("report_identity_mismatch", "实验报告没有绑定本次 Case 运行身份。")
    if trace.get("resource_binding_audit", {}).get("current") is not True:
        raise TrialError("report_resource_not_current", "实验报告的实际资源绑定未生效。")
    report = thaw_wire_mapping(case.output.get("report", {}))
    steps = _count(trace.get("steps"), "提交步骤")
    evaluations = _count(trace.get("evaluations"), "求值次数")
    formal_steps = report.get("steps", report.get("steps_executed", report.get("generation")))
    if (steps < 1 or steps > spec["max_steps"] or evaluations < 1
            or formal_steps != steps or report.get("evaluation_count") != evaluations):
        raise TrialError("progress_disagrees", "实验报告与正式 Case 的提交步骤或求值计数不一致。")
    result = trace.get("result")
    if not isinstance(result, dict):
        raise TrialError("result_missing", "实验未交付已评估的候选结果。")
    _verify_candidates(result, spec)
    # Derived display values restore the user's max/min convention. They do
    # not overwrite the authoritative raw minimization objectives in the pool.
    result = dict(result)
    problem = spec.get("problem", {})
    if problem.get("component") == "problem.expression":
        from .lab_problem import display_objectives
        result["display_objectives"] = [display_objectives(problem, row)
                                         for row in result["raw_objectives"]]
        params = problem["parameters"]
        result["objective_names"] = [row["name"] for row in params["objectives"]]
        result["objective_directions"] = [row["direction"] for row in params["objectives"]]
        result["variable_names"] = [row["name"] for row in params["variables"]]
    pool, units = trace.get("pool"), trace.get("units")
    if not isinstance(pool, dict) or not isinstance(units, (dict, list)):
        raise TrialError("state_report_missing", "实验报告未包含 Pool 与 Unit 的实际状态。")
    return {"steps": steps, "evaluations": evaluations, "report": report,
        "pool": pool, "unit": {"instances": units} if isinstance(units, list) else units,
        "results": result, "records": trace.get("records", []),
        "plan_completed": trace.get("plan_completed"),
        "resource_binding": _public_binding(binding),
        "project_result": {"run_id": run_id, "status": manifest.status, "exit_code": manifest.exit_code,
            "framework": manifest.framework, "schema_version": manifest.schema_version,
            "case_name": "search", "case_status": case.status, "case_identity": identity,
            "config_fingerprint": manifest.config_fingerprint, "report_publication": publication}}


def _verify_report_publication(project: Path, case, trace: dict) -> dict:
    from blackbase.resources import (ArtifactAuthority, FilesystemArtifactPublicationLedger,
                                    FilesystemArtifactStore)

    publication = case.artifact_publications.get("lab_report")
    ref = case.artifact_refs.get("lab_report")
    if (publication is None or ref is None or publication.ref != ref
            or publication.case_run_id != case.identity.case_run_id
            or publication.artifact_name != "lab_report"):
        raise TrialError("report_publication_missing", "实验报告未获得本次 Case 的正式 Artifact 发布收据。")
    try:
        raw_authority = case.request.resource_context["metadata"]["artifact_authority"]
        authority = ArtifactAuthority.from_dict(raw_authority)
        authority_root, target = Path(authority.root).resolve(), Path(ref.uri).resolve()
        if (not authority_root.is_relative_to(project.resolve()) or not authority_root.is_dir()
                or not target.is_relative_to(authority_root) or not target.is_file()
                or ref.size_bytes is None or not 0 < ref.size_bytes <= MAX_JSON_BYTES):
            raise ValueError("artifact scope")
        ledger = FilesystemArtifactPublicationLedger(authority,
            project_run_id=case.identity.project_run_id, case_run_id=case.identity.case_run_id)
        if not ledger.verify(publication):
            raise ValueError("publication ledger")
        data = FilesystemArtifactStore(authority.root).read_verified(ref)
        published = json.loads(data.decode("utf-8"))
        if published != trace:
            raise ValueError("report projection disagrees")
    except (ValueError, TypeError, KeyError, OSError, RuntimeError):
        raise TrialError("report_publication_invalid", "实验报告副本与正式 Artifact、摘要或发布记录不一致。") from None
    return {"publication_id": publication.publication_id,
            "receipt_digest": publication.receipt_digest, "checksum": ref.checksum,
            "size_bytes": ref.size_bytes}


def _verify_candidates(result: dict, spec: dict) -> None:
    """Check published raw feedback against the declared Problem, including constraints."""
    from nsgablack.core.state.solution_pool import SolutionRef

    refs, candidates, objectives, violations = (result.get(key) for key in
        ("refs", "candidates", "raw_objectives", "raw_violations"))
    if (not all(isinstance(values, list) for values in (refs, candidates, objectives, violations))
            or not refs or not (len(refs) == len(candidates) == len(objectives) == len(violations))
            or len(refs) > 5000):
        raise TrialError("result_alignment_invalid", "结果引用、候选与原始反馈没有逐行对齐。")
    for ref, candidate, objective, violation in zip(refs, candidates, objectives, violations):
        try:
            SolutionRef.from_dict(ref)
        except (ValueError, TypeError, KeyError, AttributeError):
            raise TrialError("result_ref_invalid", "结果缺少精确候选身份和版本。") from None
        numbers = lambda values: (isinstance(values, list) and all(
            type(value) in (int, float) and math.isfinite(value) for value in values))
        if (not numbers(candidate) or len(candidate) != spec["dimension"]
                or not numbers(objective) or not objective
                or type(violation) not in (int, float) or not math.isfinite(violation)
                or violation < 0):
            raise TrialError("result_values_invalid", "实验结果包含无效的候选维度或原始反馈。")
        problem_binding = spec.get("problem", {})
        problem = problem_binding.get("component", "problem.two_centers")
        if problem == "problem.expression":
            from .lab_problem import evaluate_problem, problem_bounds
            bounds = problem_bounds(problem_binding, spec["dimension"])
            if any(value < low - 1e-10 or value > high + 1e-10
                   for value, (low, high) in zip(candidate, bounds)):
                raise TrialError("problem_bounds_invalid", "候选超出已声明的变量边界。")
            try:
                expected, expected_violation = evaluate_problem(problem_binding, candidate)
            except (ValueError, TypeError, ArithmeticError):
                raise TrialError("problem_evaluation_invalid", "候选不满足问题公式的数值定义。") from None
            if (len(objective) != len(expected)
                    or any(not math.isclose(actual, correct, rel_tol=1e-11, abs_tol=1e-12)
                           for actual, correct in zip(objective, expected))
                    or not math.isclose(violation, expected_violation, rel_tol=1e-11, abs_tol=1e-12)):
                raise TrialError("raw_evaluation_mismatch", "池中原始目标或约束违反量与本次问题定义不一致。")
            continue
        expected_columns = 1 if problem == "problem.sphere" else 2
        if problem not in {"problem.two_centers", "problem.sphere"}:
            raise TrialError("problem_unsupported", "当前运行器没有该 Problem 的结果核对规则。")
        if (any(abs(value) > 2 for value in candidate) or violation != 0
                or len(objective) != expected_columns):
            raise TrialError("problem_bounds_invalid", "结果不满足示例 Problem 的边界和原始可行性。")
        expected = ([sum(value ** 2 for value in candidate)] if problem == "problem.sphere" else
                    [sum((value - (center if index == 0 else 0)) ** 2
                         for index, value in enumerate(candidate)) for center in (-1, 1)])
        if any(not math.isclose(actual, correct, rel_tol=1e-11, abs_tol=1e-12)
               for actual, correct in zip(objective, expected)):
            raise TrialError("raw_evaluation_mismatch", "池中原始目标与示例 Problem 的真实求值不一致。")


def run_trial(spec: Mapping[str, Any], *, timeout_seconds: float = 60) -> dict:
    """Run one checked assembly; return JSON evidence without keeping host paths."""
    started = time.monotonic()
    result = {"schema": RESULT_SCHEMA, "status": "failed", "success": False, "error": None,
              "logs": "", "duration_seconds": 0.0, "exit_code": None,
              "steps": 0, "evaluations": 0, "report": {}, "pool": {}, "unit": {},
              "results": {}, "records": [], "resource_binding": {}, "project_result": {}}
    try:
        from .lab_project import export_project, normalize_spec

        if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
                or not 1 <= timeout_seconds <= 90):
            raise TrialError("timeout_invalid", "试跑超时必须为 1 到 90 秒。")
        try:
            normalized = normalize_spec(spec)
        except (ValueError, TypeError, KeyError):
            raise TrialError("spec_invalid", "装配配方或参数不在实验台支持范围内。") from None
        result["spec"] = normalized
        run_id = "lab-" + uuid4().hex
        with tempfile.TemporaryDirectory(prefix="nsgablack-lab-") as temporary:
            root = Path(temporary).resolve()
            project = export_project(normalized, root / "project")
            if not isinstance(project, Path) or project.resolve() != root / "project":
                raise TrialError("export_scope_invalid", "配方导出未返回本次独立 Project。")
            env = _trial_environment(root)
            code, logs, timed_out = _execute(project, run_id, env, float(timeout_seconds))
            result["exit_code"] = code
            # The child has no secrets, but tracebacks may contain deployment or
            # temporary paths. Keep relevant diagnostics without revealing these.
            result["logs"] = _public_logs(logs, root)
            if timed_out:
                raise TrialError("trial_timeout", "试跑超过时间上限，已终止本次 Project 及子进程。")
            if code != 0:
                raise TrialError("project_exit_nonzero", "正式 Project 运行失败，请查看运行日志。")
            result.update(_verify_receipts(project, normalized, run_id))
            result.update(status="succeeded", success=True)
    except TrialError as exc:
        result["error"] = {"code": exc.code, "message": str(exc)}
    except (OSError, ValueError, TypeError, KeyError, ImportError, RuntimeError):
        result["error"] = {"code": "trial_runtime_error", "message": "私有运行器未能完成实验，请检查安装与运行收据。"}
    result["duration_seconds"] = round(time.monotonic() - started, 6)
    return result


__all__ = ["RESULT_SCHEMA", "run_trial"]
