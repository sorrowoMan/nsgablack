"""One client boundary for the local workbench and private hosted trial worker."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, ProxyHandler
import uuid

from .lab_jobs import LabJobError

_manager = None
_lock = threading.Lock()


class LabClientError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _hosted() -> bool:
    return os.environ.get("NSGABLACK_CATALOG_HOSTED", "").strip() == "1"


def _remote_config(environment_key: str = "NSGABLACK_LAB_CLIENT_CONFIG") -> dict | None:
    source = os.environ.get(environment_key, "")
    if not source:
        return None
    try:
        path = Path(source)
        if not path.is_file() or path.stat().st_size > 4096:
            raise ValueError()
        config = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(config, dict) or set(config) != {"url", "token"}:
            raise ValueError()
        url = urlsplit(config["url"])
        if (url.scheme != "http" or not url.hostname or not url.port
                or url.username or url.password or url.path not in {"", "/"}
                or url.query or url.fragment or "\\" in config["url"]
                or not re.fullmatch(r"[A-Za-z0-9._:-]+", url.netloc)
                or not re.fullmatch(r"[a-f0-9]{64}", config["token"])):
            raise ValueError()
        return {"url": config["url"].rstrip("/"), "token": config["token"]}
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        raise LabClientError("实验台运行服务配置无效，请联系维护者。") from None


def _request(config: dict, path: str, body: dict | None = None, *, timeout: float = 8) -> dict:
    request = Request(config["url"] + path,
                      data=None if body is None else json.dumps(body, ensure_ascii=False, allow_nan=False).encode(),
                      headers={"Authorization": "Bearer " + config["token"],
                               "Content-Type": "application/json"},
                      method="GET" if body is None else "POST")
    try:
        # The endpoint is deployment-owned; never send credentials through an
        # ambient HTTP proxy or redirect to a different service.
        with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=timeout) as response:
            data = response.read(2 * 1024 * 1024 + 1)
            if len(data) > 2 * 1024 * 1024:
                raise LabClientError("运行服务返回的结果过大。")
            result = json.loads(data)
            if not isinstance(result, dict):
                raise ValueError()
            return result
    except HTTPError as exc:
        if exc.code in {400, 404, 409, 429}:
            try:
                error = json.loads(exc.read(4096)).get("error", {})
                messages = {"queue_full": "试跑队列已满，请稍后重试。",
                            "job_missing": "试跑记录已过期或服务已重启，请重新试跑。",
                            "invalid_spec": "装配参数不符合组件契约，请检查后重试。",
                            "budget_exhausted": "AI 服务达到管理员配置的请求上限，请调整服务配置后继续。",
                            "request_conflict": "同一请求不能更换指令或装配内容。"}
                raise LabClientError(messages.get(error.get("code"), "运行请求未被接纳。")) from None
            except (ValueError, AttributeError):
                pass
        raise LabClientError("无法访问实验台运行服务，请稍后重试。") from None
    except (OSError, URLError, ValueError, UnicodeError):
        raise LabClientError("实验台运行服务暂不可用，请稍后重试。") from None


def get_capabilities() -> dict:
    from .lab_project import list_recipes
    from .lab_assembly import assembly_catalog
    recipes = list(list_recipes())
    catalog = assembly_catalog()
    try:
        config = _remote_config()
        if config:
            remote = _request(config, "/capabilities", timeout=2)
            limits = remote.get("limits")
            if (remote.get("schema") != "nsgablack.lab.capabilities/v1"
                    or not isinstance(limits, dict) or limits.get("parallel") != 1
                    or limits.get("timeout_seconds") != 60 or remote.get("recipes") != recipes
                    or remote.get("assembly_catalog") != catalog):
                raise LabClientError("实验台运行服务版本不匹配。")
            return {"enabled": True, "mode": "remote", "reason": "独立 CPU 试跑服务",
                    "recipes": recipes, "assembly_catalog": catalog, "limits": limits}
        if _hosted():
            return {"enabled": False, "mode": "unavailable", "recipes": recipes, "assembly_catalog": catalog,
                    "reason": "当前部署尚未接入独立运行服务；可预览并下载正式 Project。"}
        return {"enabled": True, "mode": "local", "reason": "本机 CPU 试跑",
                "recipes": recipes, "assembly_catalog": catalog, "limits": {"timeout_seconds": 60, "parallel": 1}}
    except LabClientError as exc:
        return {"enabled": False, "mode": "unavailable", "recipes": recipes,
                "assembly_catalog": catalog, "reason": str(exc)}


def _local_manager():
    global _manager
    if _hosted():
        raise LabClientError("托管 Catalog 不在网页进程中执行算法。")
    with _lock:
        if _manager is None:
            from .lab_jobs import JobManager
            from .lab_project_sources import ProjectSourceRegistry
            _manager = JobManager(project_sources=ProjectSourceRegistry())
    return _manager


def submit(spec, *, request_id: str | None = None) -> dict:
    from .lab_project import normalize_spec
    normalized = normalize_spec(spec)
    request_id = uuid.uuid4().hex if request_id is None else request_id
    if not isinstance(request_id, str) or not re.fullmatch(r"[0-9a-f]{32}", request_id):
        raise LabClientError("提交身份无效。")
    config = _remote_config()
    if config:
        return _request(config, "/jobs", {"request_id": request_id, "spec": normalized})
    try:
        return _local_manager().submit(normalized, request_id=request_id)
    except LabJobError as exc:
        raise LabClientError(str(exc)) from None


def poll(job_id: str) -> dict:
    if not isinstance(job_id, str) or not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise LabClientError("试跑身份无效。")
    config = _remote_config()
    if config:
        return _request(config, "/jobs/" + job_id)
    try:
        return _local_manager().poll(job_id)
    except LabJobError as exc:
        raise LabClientError(str(exc)) from None


def assistant_capabilities() -> dict:
    """Only a private draft service holds a model grant; manual editing is independent."""
    from .lab_assembly import assembly_catalog
    try:
        config = _remote_config("NSGABLACK_LAB_ASSISTANT_CLIENT_CONFIG")
        if config is None:
            return {"enabled": False, "mode": "unavailable",
                    "reason": "尚未接入 AI 装配助手；手动装配与试跑可以继续使用。"}
        value = _request(config, "/capabilities", timeout=2)
        if (value.get("schema") != "nsgablack.lab.assistant_capabilities/v1"
                or value.get("assembly_catalog") != assembly_catalog()):
            raise LabClientError("AI 助手与当前装配契约版本不匹配。")
        if value.get("enabled") is not True or value.get("drafts_only") is not True:
            raise LabClientError("AI 装配助手暂不可用，手动装配仍可使用。")
        return {**value, "mode": "remote"}
    except LabClientError as exc:
        return {"enabled": False, "mode": "unavailable", "reason": str(exc)}


def assistant_submit(spec, instruction: str, *, request_id: str | None = None, guide_context=None) -> dict:
    from .lab_assembly import normalize_assembly
    try:
        normalized = normalize_assembly(spec)
    except (ValueError, TypeError):
        raise LabClientError("请先修正装配参数，再请求 AI 修改。") from None
    if (not isinstance(instruction, str) or not 1 <= len(instruction.strip()) <= 4000
            or len(instruction.encode("utf-8")) > 12000):
        raise LabClientError("请填写不超过 4000 字、12 KiB 的修改说明。")
    request_id = uuid.uuid4().hex if request_id is None else request_id
    if not isinstance(request_id, str) or not re.fullmatch(r"[0-9a-f]{32}", request_id):
        raise LabClientError("提交身份无效。")
    config = _remote_config("NSGABLACK_LAB_ASSISTANT_CLIENT_CONFIG")
    if config is None:
        raise LabClientError("AI 装配助手尚未接入，手动装配仍可使用。")
    body = {"spec": normalized, "instruction": instruction.strip(), "request_id": request_id}
    if guide_context is not None:
        from .lab_guide import normalize_guide_context
        from .lab_jobs import spec_digest
        try:
            body["guide_context"] = normalize_guide_context(guide_context, base_digest=spec_digest(normalized))
        except (ValueError, TypeError):
            raise LabClientError("AI 引导上下文不完整，请刷新对应步骤后重试。") from None
    return _request(config, "/jobs", body)


def assistant_poll(job_id: str) -> dict:
    if not isinstance(job_id, str) or not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise LabClientError("AI 草稿身份无效。")
    config = _remote_config("NSGABLACK_LAB_ASSISTANT_CLIENT_CONFIG")
    if config is None:
        raise LabClientError("AI 装配助手尚未接入。")
    return _request(config, "/jobs/" + job_id)


def _project_identity(value: str | None = None) -> str:
    value = uuid.uuid4().hex if value is None else value
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value):
        raise LabClientError("项目请求身份无效。")
    return value


def project_capabilities() -> dict:
    """Advertise only Projects whose source revision matches both services."""
    try:
        assistant = _remote_config("NSGABLACK_LAB_ASSISTANT_CLIENT_CONFIG")
        if assistant is None:
            return {"enabled": False, "projects": [], "reason": "项目协作助手尚未配置。"}
        ai = _request(assistant, "/project/capabilities", timeout=10)
        worker = _remote_config()
        trial = (_request(worker, "/project/capabilities", timeout=10) if worker
                 else _local_manager().project_capabilities())
        if ai.get("enabled") is not True or trial.get("enabled") is not True:
            return {"enabled": False, "projects": [], "reason": "项目资料或独立试跑服务尚未接通。"}
        available = {p["project_id"]: p for p in trial.get("projects", [])}
        projects = [p for p in ai.get("projects", [])
                    if p.get("project_id") in available
                    and p.get("source_digest") == available[p["project_id"]].get("source_digest")]
        return {**ai, "enabled": bool(projects), "projects": projects,
                "trial_limits": trial.get("limits", {}),
                "reason": "读取已有项目、提出配置并通过正式入口试跑。" if projects else "项目源码版本尚未对齐。"}
    except LabClientError as exc:
        return {"enabled": False, "projects": [], "reason": str(exc)}


def project_assistant_submit(project_id: str, instruction: str, *, request_id=None,
                             history=None, proposal=None, trial=None) -> dict:
    config = _remote_config("NSGABLACK_LAB_ASSISTANT_CLIENT_CONFIG")
    if config is None:
        raise LabClientError("项目协作助手尚未配置。")
    if (not isinstance(project_id, str) or not 1 <= len(project_id) <= 240
            or not isinstance(instruction, str) or not 1 <= len(instruction.strip()) <= 4000):
        raise LabClientError("请选择项目并填写问题。")
    body = {"request_id": _project_identity(request_id), "project_id": project_id,
            "instruction": instruction.strip(), "history": list(history or []),
            "proposal": proposal, "trial": trial}
    return _request(config, "/project/jobs", body)


def project_assistant_poll(job_id: str) -> dict:
    config = _remote_config("NSGABLACK_LAB_ASSISTANT_CLIENT_CONFIG")
    if config is None:
        raise LabClientError("项目协作助手尚未配置。")
    return _request(config, "/project/jobs/" + _project_identity(job_id))


def project_trial_submit(proposal, *, request_id=None) -> dict:
    from .lab_jobs import spec_digest
    body = {"request_id": _project_identity(request_id), "spec": proposal,
            "confirmed_digest": spec_digest(proposal)}
    config = _remote_config()
    if config:
        return _request(config, "/project/jobs", body)
    try:
        return _local_manager().submit_project(proposal, request_id=body["request_id"],
                                              confirmed_digest=body["confirmed_digest"])
    except (LabJobError, ValueError) as exc:
        raise LabClientError("项目配置或版本未通过运行校验。") from None


def project_trial_poll(job_id: str) -> dict:
    identity = _project_identity(job_id)
    config = _remote_config()
    if config:
        return _request(config, "/project/jobs/" + identity)
    try:
        return _local_manager().poll(identity)
    except LabJobError as exc:
        raise LabClientError(str(exc)) from None


def project_result_reader():
    """An assistant-only, GET-only grant; never borrow a runner write token."""
    config = _remote_config("NSGABLACK_PROJECT_RESULT_CLIENT_CONFIG")
    if config is None:
        return None

    def read(job_id):
        return _request(config, "/project/jobs/" + _project_identity(job_id), timeout=10)

    return read
