"""Project-backed collaboration, separate from the small assembly workbench.

Rendering only reads capabilities and polls known jobs. A model proposal needs
an explicit adoption action, followed by an independent trial action. The UI
never executes model code and never supplies browser-authored result metrics.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import base64
import hashlib
import json
import re
import time
from typing import Any
from uuid import uuid4

from .lab_jobs import spec_digest
from .ui_theme import WORKSPACE_CSS

_PREFIX = "catalog_project::"
_CAPS_KEY = _PREFIX + "capabilities"
_PROJECT_KEY = _PREFIX + "project"
_SELECTION_KEY = _PREFIX + "selection"
_HISTORY_KEY = _PREFIX + "history"
_PROPOSAL_KEY = _PREFIX + "adopted_proposal"
_AI_JOB_KEY = _PREFIX + "assistant_job"
_AI_INTENT_KEY = _PREFIX + "assistant_submission"
_TRIAL_JOB_KEY = _PREFIX + "trial_job"
_TRIAL_INTENT_KEY = _PREFIX + "trial_submission"
_TRIAL_BINDING_KEY = _PREFIX + "trial_binding"
_INSTRUCTION_KEY = _PREFIX + "instruction"
_SEEN_KEY = _PREFIX + "seen_answers"
_ACTIVE = frozenset({"queued", "running"})
_TERMINAL = frozenset({"succeeded", "failed", "timed_out"})
_MAX_ARCHIVE_BYTES = 512 * 1024
_STYLES = WORKSPACE_CSS + """
<style>
.st-key-catalog_project_workspace {min-width:0;}
.st-key-catalog_project_discussion,.st-key-catalog_project_proposal {
 background:var(--workspace-card);border:1px solid var(--catalog-line);
 border-radius:var(--workspace-radius);padding:1.35rem;min-width:0;
}
.project-workspace-heading {color:var(--catalog-ink);font-size:1.7rem;
 font-weight:700;letter-spacing:-.03em;line-height:1.4;margin:0 0 .3rem;}
.project-workspace-copy {color:var(--catalog-muted);font-size:.9rem;
 line-height:1.8;margin:0 0 1.1rem;}
</style>
"""


def _digest(value: Mapping | None) -> str:
    return spec_digest(value) if isinstance(value, Mapping) else "none"


def _validated_archive(value: Mapping) -> tuple[bytes, dict]:
    """Verify the bounded download payload without extracting any ZIP entry."""
    if not isinstance(value, Mapping):
        raise ValueError("invalid_artifact_archive")
    filename, encoded, checksum, size = (value.get(key) for key in
                                       ("filename", "base64", "sha256", "size_bytes"))
    if (not isinstance(filename, str) or not 1 <= len(filename) <= 160
            or filename.strip() != filename or not filename.lower().endswith(".zip")
            or any(char in filename for char in "/\\:")
            or any(ord(char) < 32 for char in filename)
            or not isinstance(encoded, str)
            or len(encoded) > ((_MAX_ARCHIVE_BYTES + 2) // 3) * 4
            or not isinstance(checksum, str) or type(size) is not int
            or not 1 <= size <= _MAX_ARCHIVE_BYTES
            or type(value.get("truncated", False)) is not bool):
        raise ValueError("invalid_artifact_archive")
    checksum = checksum.removeprefix("sha256:").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise ValueError("invalid_artifact_archive")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid_artifact_archive") from exc
    if len(payload) != size or hashlib.sha256(payload).hexdigest() != checksum:
        raise ValueError("artifact_archive_integrity_failed")
    return payload, {"filename": filename, "sha256": checksum, "size_bytes": size,
                     "truncated": value.get("truncated", False)}


def _report_metadata(result: Mapping) -> dict:
    report = deepcopy(dict(result))
    if isinstance(report.get("artifact_archive"), Mapping):
        report["artifact_archive"] = {key: value for key, value in report["artifact_archive"].items()
                                      if key != "base64"}
    return report


def _render_artifact_download(st: Any, archive) -> None:
    if archive is None:
        return
    try:
        payload, metadata = _validated_archive(archive)
    except ValueError:
        st.warning("本次运行的产物包未通过大小或摘要校验，暂不提供下载；运行报告仍可查看。")
        return
    st.download_button("下载本次运行产物 ZIP", payload, file_name=metadata["filename"],
        mime="application/zip", key=_PREFIX + "download_artifacts", on_click="ignore")
    if metadata["truncated"]:
        st.caption("产物较多，ZIP 仅包含本轮已核验的部分文件；完整产物清单见运行记录。")
    else:
        st.caption("下载包来自本次正式运行，大小与 SHA-256 已校验；文件不会在页面中解压或执行。")


def _reset_project(state, project_id: str) -> None:
    if state.get(_PROJECT_KEY) == project_id:
        return
    for name in (_HISTORY_KEY, _PROPOSAL_KEY, _AI_JOB_KEY, _AI_INTENT_KEY,
                 _TRIAL_JOB_KEY, _TRIAL_INTENT_KEY, _TRIAL_BINDING_KEY,
                 _INSTRUCTION_KEY, _SEEN_KEY):
        state.pop(name, None)
    state[_PROJECT_KEY] = project_id


def _current_trial(state, project_id: str) -> str | None:
    """Only reference service-owned evidence for the adopted configuration."""
    job = state.get(_TRIAL_JOB_KEY) or {}
    binding = state.get(_TRIAL_BINDING_KEY) or {}
    if (job.get("status") in _TERMINAL
            and binding.get("project_id") == project_id
            and binding.get("proposal_digest") == _digest(state.get(_PROPOSAL_KEY))
            and isinstance(job.get("job_id"), str)):
        return job["job_id"]
    return None


def _capabilities(st: Any, supplied=None) -> dict:
    if supplied is not None:
        return dict(supplied)
    from . import lab_client
    saved = st.session_state.get(_CAPS_KEY)
    now = time.monotonic()
    if saved and 0 <= now - saved["at"] < 15:
        return deepcopy(saved["value"])
    try:
        value = dict(lab_client.project_capabilities())
    except lab_client.LabClientError as exc:
        value = {"enabled": False, "projects": [], "reason": str(exc)}
    st.session_state[_CAPS_KEY] = {"at": now, "value": deepcopy(value)}
    return value


def _remember_answer(st: Any, job: Mapping, result: Mapping) -> None:
    seen = list(st.session_state.get(_SEEN_KEY, []))
    identity = job.get("job_id")
    if identity in seen:
        return
    history = list(st.session_state.get(_HISTORY_KEY, []))
    for role, text in (("user", job.get("ui_instruction", "")),
                       ("assistant", result.get("explanation", ""))):
        if str(text).strip():
            history.append({"role": role, "content": str(text)[:600]})
    st.session_state[_HISTORY_KEY] = history[-6:]
    st.session_state[_SEEN_KEY] = [*seen, identity][-12:]


def _render_progress(st: Any, progress) -> None:
    if not isinstance(progress, Mapping):
        return
    counts = []
    for key, label in (("model_calls", "模型请求"), ("tool_calls", "已完成工具调用")):
        value = progress.get(key)
        if type(value) is int and value >= 0:
            counts.append(f"{label} {value} 次")
    if counts:
        st.caption(" · ".join(counts))
    trace = progress.get("tool_trace")
    if not isinstance(trace, list):
        return
    names = {"project_files": "列出文件", "project_read": "读取资料", "project_find": "定位源码", "project_data": "检查数据",
             "project_parameters": "核对参数", "propose_project_trial": "校验方案",
             "project_result": "读取本轮结果"}
    for row in trace[-3:]:
        if not isinstance(row, Mapping):
            continue
        name = row.get("name")
        if name not in names:
            continue
        arguments = row.get("arguments") or {}
        target = (arguments.get("path") or arguments.get("case_name") or arguments.get("job_id")) if isinstance(arguments, Mapping) else None
        label = names[name]
        if isinstance(target, str):
            label += " · " + target[:160]
        if row.get("ok") is False:
            label += "（需调整）"
        st.caption(label)


def _render_answer(st: Any, project_id: str) -> None:
    from . import lab_client
    saved = st.session_state.get(_AI_JOB_KEY)
    if not saved:
        return
    if st.button("刷新项目 AI", key=_PREFIX + "refresh_assistant") or saved.get("status") in _ACTIVE:
        try:
            updated = dict(lab_client.project_assistant_poll(saved["job_id"]))
        except lab_client.LabClientError as exc:
            st.warning(f"暂时无法读取项目讨论：{exc}")
        else:
            was_active = saved.get("status") in _ACTIVE
            saved = {**updated, "ui_instruction": saved.get("ui_instruction", ""),
                     "ui_base_proposal_digest": saved.get("ui_base_proposal_digest")}
            st.session_state[_AI_JOB_KEY] = saved
            if was_active and saved.get("status") not in _ACTIVE:
                st.rerun()
    if saved.get("status") in _ACTIVE:
        st.info("AI 正在读取项目资料并整理方案，尚未启动试跑。")
        _render_progress(st, saved.get("progress"))
        return
    if saved.get("status") == "failed":
        error = saved.get("error") or {}
        st.error(str(error.get("message", "项目讨论未完成，请保留当前方案后重试。")))
        return
    result = saved.get("result") or {}
    if result.get("project_id") != project_id:
        st.warning("这份回答属于其他项目，不能应用到当前项目。")
        return
    _remember_answer(st, saved, result)
    if result.get("explanation"):
        st.markdown(str(result["explanation"]))
    for question in result.get("questions") or []:
        st.info(str(question))
    trace = result.get("tool_trace")
    if trace:
        with st.expander("AI 本轮读取与检查的依据", expanded=False):
            st.json(trace)
    if result.get("model_calls") is not None:
        st.caption(f"本轮模型请求 {result['model_calls']} 次；方案生成与正式运行分别记录。")


def _render_discussion(st: Any, project_id: str, capabilities: Mapping) -> None:
    from . import lab_client
    st.subheader("围绕现有项目讨论")
    st.caption("可以描述业务、修改一个偏好，或让 AI 根据本轮结果继续调整。")
    instruction = st.text_area("这次想完成什么", key=_INSTRUCTION_KEY, height=170, max_chars=4000,
        placeholder="先读这个项目的模型、数据与装配，说明已有能力；再为我的想法提出一个小预算方案。")
    job = st.session_state.get(_AI_JOB_KEY) or {}
    active = job.get("status") in _ACTIVE
    intent = st.session_state.get(_AI_INTENT_KEY)
    if intent:
        st.warning("上次 AI 提交尚未确认。内容相同时再次提交会沿用原请求身份。")
    if st.button("请 AI 读取项目并讨论", type="primary", key=_PREFIX + "ask",
                 width="stretch", disabled=not capabilities.get("enabled") or not instruction.strip() or active):
        payload = {"project_id": project_id, "instruction": instruction.strip(),
                   "history": deepcopy(st.session_state.get(_HISTORY_KEY, [])),
                   "proposal": deepcopy(st.session_state.get(_PROPOSAL_KEY)),
                   "trial": _current_trial(st.session_state, project_id)}
        fingerprint = spec_digest(payload)
        if not intent or intent.get("fingerprint") != fingerprint:
            intent = {"request_id": uuid4().hex, "fingerprint": fingerprint, "payload": payload}
            st.session_state[_AI_INTENT_KEY] = intent
        frozen = intent["payload"]
        try:
            submitted = lab_client.project_assistant_submit(
                frozen["project_id"], frozen["instruction"], request_id=intent["request_id"],
                history=frozen["history"], proposal=frozen["proposal"], trial=frozen["trial"])
        except lab_client.LabClientError as exc:
            st.error(f"未能确认项目 AI 请求：{exc}")
        else:
            st.session_state[_AI_JOB_KEY] = {**dict(submitted),
                "ui_instruction": frozen["instruction"],
                "ui_base_proposal_digest": _digest(frozen["proposal"])}
            st.session_state.pop(_AI_INTENT_KEY, None)
            st.rerun()

    @st.fragment(run_every="2s" if active else None)
    def answer_status():
        _render_answer(st, project_id)
    answer_status()


def _render_proposal(st: Any, project_id: str, capabilities: Mapping) -> None:
    from . import lab_client
    st.subheader("下一次运行的方案")
    job = st.session_state.get(_AI_JOB_KEY) or {}
    result = job.get("result") or {}
    pending = result.get("proposal")
    adopted = st.session_state.get(_PROPOSAL_KEY)
    if job.get("status") == "succeeded" and not isinstance(pending, Mapping):
        st.caption("本轮没有交付经校验的新方案。文字建议不会替换已采用配置。")
    if isinstance(pending, Mapping):
        offered_here = result.get("project_id") == project_id and pending.get("project_id") == project_id
        stale = job.get("ui_base_proposal_digest") != _digest(adopted)
        already_adopted = _digest(pending) == _digest(adopted)
        st.caption("AI 建议 · 采用前不会改变当前方案")
        st.json(pending)
        if not offered_here:
            st.warning("提案的项目身份与当前项目不一致，不能采用。")
        elif stale and not already_adopted:
            st.warning("当前方案已经改变，这份旧提案不能覆盖新方案。请继续讨论后重新生成。")
        if st.button("当前已采用" if already_adopted else "采用这个方案", key=_PREFIX + "adopt",
                     width="stretch", disabled=not offered_here or stale or already_adopted):
            st.session_state[_PROPOSAL_KEY] = deepcopy(dict(pending))
            st.rerun()
    elif not adopted:
        st.info("AI 读完资料后，可在这里交付带参数和预算的方案。讨论本身不会运行项目。")
    if adopted:
        with st.expander("已采用的完整配置", expanded=not isinstance(pending, Mapping)):
            st.json(adopted)
        st.caption("仅运行已采用的配置。CPU、步数和超时由正式运行服务校验，模型文本不会作为命令执行。")
        saved = st.session_state.get(_TRIAL_JOB_KEY) or {}
        active = saved.get("status") in _ACTIVE
        intent = st.session_state.get(_TRIAL_INTENT_KEY)
        if intent:
            st.warning("上次试跑提交尚未确认。再次运行相同方案会沿用原请求身份。")
        if st.button("运行已采用方案", type="primary", key=_PREFIX + "run", width="stretch",
                     disabled=not capabilities.get("trial_enabled", capabilities.get("enabled")) or active):
            fingerprint = _digest(adopted)
            if not intent or intent.get("proposal_digest") != fingerprint:
                intent = {"request_id": uuid4().hex, "proposal_digest": fingerprint,
                          "proposal": deepcopy(dict(adopted))}
                st.session_state[_TRIAL_INTENT_KEY] = intent
            try:
                submitted = lab_client.project_trial_submit(intent["proposal"], request_id=intent["request_id"])
            except lab_client.LabClientError as exc:
                st.error(f"未能确认项目试跑：{exc}")
            else:
                st.session_state[_TRIAL_JOB_KEY] = dict(submitted)
                st.session_state[_TRIAL_BINDING_KEY] = {"project_id": project_id,
                    "proposal_digest": intent["proposal_digest"]}
                st.session_state.pop(_TRIAL_INTENT_KEY, None)
                st.rerun()


def _render_trial(st: Any, project_id: str) -> None:
    from . import lab_client
    saved = st.session_state.get(_TRIAL_JOB_KEY)
    if not saved:
        return
    if st.button("刷新项目运行", key=_PREFIX + "refresh_trial") or saved.get("status") in _ACTIVE:
        try:
            updated = dict(lab_client.project_trial_poll(saved["job_id"]))
        except lab_client.LabClientError as exc:
            st.warning(f"暂时无法读取项目运行：{exc}")
        else:
            was_active = saved.get("status") in _ACTIVE
            saved = updated
            st.session_state[_TRIAL_JOB_KEY] = saved
            if was_active and saved.get("status") not in _ACTIVE:
                st.rerun()
    binding = st.session_state.get(_TRIAL_BINDING_KEY) or {}
    current = (binding.get("project_id") == project_id
               and binding.get("proposal_digest") == _digest(st.session_state.get(_PROPOSAL_KEY)))
    if not current:
        st.warning("下方是旧方案的运行记录，不作为当前方案的验证或下一次 AI 的本轮证据。")
    if saved.get("status") in _ACTIVE:
        st.info("正式 Project 正在排队。" if saved["status"] == "queued" else "正式 Project 正在运行。")
        return
    result = saved.get("result") or {}
    if saved.get("status") == "succeeded":
        st.success("Project 运行完成；业务可行性与指标请查看下方真实报告。")
    elif saved.get("status") in {"failed", "timed_out"}:
        error = saved.get("error") or result.get("error") or {}
        st.error(str(error.get("message", "项目运行未完成。")))
    columns = st.columns(3)
    columns[0].metric("逻辑提交步", result.get("steps", "—"))
    columns[1].metric("实际评估次数", result.get("evaluations", "—"))
    duration = result.get("duration_seconds", result.get("elapsed_seconds"))
    columns[2].metric("本轮耗时", f"{duration:.2f} s" if isinstance(duration, (int, float)) else "—")
    metrics = result.get("metrics", result.get("business_metrics"))
    if metrics:
        st.markdown("**本轮业务指标与约束**")
        st.json(metrics)
    _render_artifact_download(st, result.get("artifact_archive"))
    report = _report_metadata(result)
    with st.expander("正式运行记录与原始依据", expanded=False):
        st.json(report)
    download_record = {**dict(saved), "result": report}
    st.download_button("下载本轮项目运行记录", json.dumps(download_record, ensure_ascii=False, indent=2),
        file_name=f"project_trial_{str(saved.get('job_id', 'result'))[:12]}.json",
        mime="application/json", key=_PREFIX + "download_trial", on_click="ignore")


def render_project_workbench(st: Any, capabilities=None) -> None:
    """Read an existing Project, review a proposal, then independently run it."""
    st.markdown(_STYLES, unsafe_allow_html=True)
    caps = _capabilities(st, capabilities)
    with st.container(key="catalog_project_workspace"):
        st.markdown("<div class='project-workspace-heading'>和 AI 一起推进已有项目</div>"
                    "<div class='project-workspace-copy'>读取真实模型与数据，讨论一个改动，"
                    "采用方案后用正式 Project 验证，再依据本轮结果继续。</div>", unsafe_allow_html=True)
        if st.button("刷新项目连接", key=_PREFIX + "refresh_capabilities"):
            st.session_state.pop(_CAPS_KEY, None)
            st.rerun()
        projects = {str(row["project_id"]): dict(row) for row in caps.get("projects", [])
                    if isinstance(row, Mapping) and isinstance(row.get("project_id"), str)}
        if not projects:
            st.info(str(caps.get("reason") or "尚未发现可协作的正式 Project，请检查项目资料连接。"))
            return
        project_id = st.selectbox("选择已有 Project", list(projects), key=_SELECTION_KEY,
            format_func=lambda key: str(projects[key].get("title") or key))
        _reset_project(st.session_state, project_id)
        selected = projects[project_id]
        if selected.get("description"):
            st.caption(str(selected["description"]))
        if not caps.get("enabled"):
            st.warning(str(caps.get("reason") or "AI 项目协作服务暂不可用，已有方案与运行记录仍保留。"))
        columns = st.columns([1.15, 1], gap="large")
        with columns[0], st.container(key="catalog_project_discussion"):
            _render_discussion(st, project_id, caps)
        with columns[1], st.container(key="catalog_project_proposal"):
            _render_proposal(st, project_id, caps)
        active = (st.session_state.get(_TRIAL_JOB_KEY) or {}).get("status") in _ACTIVE
        @st.fragment(run_every="2s" if active else None)
        def trial_status():
            _render_trial(st, project_id)
        trial_status()
