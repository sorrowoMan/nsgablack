"""Project UI actions preserve explicit adoption, execution and evidence binding."""
from __future__ import annotations

from copy import deepcopy
import base64
import hashlib
import io
import zipfile

import pytest

from nsgablack.catalog import lab_client, lab_project_ui as ui

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


def _widget(elements, label):
    return next(item for item in elements if item.label == label)


def _ok(app):
    assert not app.exception, [row.message for row in app.exception]


def _proposal(project_id="production", *, weight=0.01):
    return {"schema": "nsgablack.project_trial/v1", "project_id": project_id,
            "project_revision": "a" * 64, "case_name": "production",
            "parameters": {"smoothness_penalty": weight},
            "budget": {"max_steps": 8, "timeout_seconds": 60, "threads": 1, "gpus": 0},
            "seed": 42}


@pytest.fixture
def client(monkeypatch):
    state = {"assistant_submissions": [], "assistant_polls": [], "trial_submissions": [],
             "trial_polls": [], "proposal": _proposal(), "assistant_status": "succeeded",
             "trial_status": "succeeded", "assistant_submit_error": False,
             "trial_submit_error": False, "trial_poll_error": False}

    def caps():
        return {"enabled": True, "trial_enabled": True, "projects": [
            {"project_id": "production", "title": "生产排程"},
            {"project_id": "second", "title": "另一个项目"}]}

    def assistant_submit(project_id, instruction, *, request_id=None, history=None, proposal=None, trial=None):
        state["assistant_submissions"].append({"project_id": project_id, "instruction": instruction,
            "request_id": request_id, "history": deepcopy(history), "proposal": deepcopy(proposal),
            "trial": trial})
        if state["assistant_submit_error"]:
            raise lab_client.LabClientError("响应丢失，状态未确认")
        return {"job_id": "a" * 32, "status": "queued"}

    def assistant_poll(job_id):
        state["assistant_polls"].append(job_id)
        return {"job_id": job_id, "status": state["assistant_status"], "progress": state.get("progress"), "result": {
            "schema": "nsgablack.project_assistant_result/v1", "project_id": "production",
            "explanation": "已读取现有问题和参数，建议先保留原模型再试跑。",
            "questions": [], "proposal": deepcopy(state["proposal"]),
            "tool_trace": [{"tool": "read_source", "path": "problem.py", "sha256": "b" * 64}],
            "model_calls": 2, "verification_status": "not_run"}}

    def trial_submit(proposal, *, request_id=None):
        state["trial_submissions"].append({"proposal": deepcopy(proposal), "request_id": request_id})
        if state["trial_submit_error"]:
            raise lab_client.LabClientError("运行提交未确认")
        return {"job_id": "b" * 32, "status": "queued"}

    def trial_poll(job_id):
        state["trial_polls"].append(job_id)
        if state["trial_poll_error"]:
            raise lab_client.LabClientError("运行服务暂时不可用")
        result = {"steps": 8, "evaluations": 20, "duration_seconds": 2.5,
            "metrics": {"total_production": 1234, "raw_violations": [0.]},
            "run_id": "current-run", "resource_binding": {"current": True}}
        if state["trial_status"] in {"failed", "timed_out"}:
            result["error"] = {"code": "trial_timeout", "message": "试跑超时，未交付最终结果。"}
        if "artifact_archive" in state:
            result["artifact_archive"] = deepcopy(state["artifact_archive"])
        return {"job_id": job_id, "status": state["trial_status"], "result": result}

    for name, func in (("project_capabilities", caps),
                       ("project_assistant_submit", assistant_submit),
                       ("project_assistant_poll", assistant_poll),
                       ("project_trial_submit", trial_submit), ("project_trial_poll", trial_poll)):
        monkeypatch.setattr(lab_client, name, func, raising=False)
    return state


@pytest.fixture
def app(client):
    return AppTest.from_string(
        "import streamlit as st\n"
        "from nsgablack.catalog.lab_project_ui import render_project_workbench\n"
        "render_project_workbench(st)\n", default_timeout=30).run()


def _ask(app, text="先读取当前项目，再给一个小预算方案。"):
    _widget(app.text_area, "这次想完成什么").set_value(text).run()
    return _widget(app.button, "请 AI 读取项目并讨论").click().run()


def _adopt(app):
    return _widget(app.button, "采用这个方案").click().run()


def test_browsing_project_never_submits_model_or_trial(app, client):
    _ok(app)
    assert _widget(app.selectbox, "选择已有 Project").value == "production"
    app.run()
    assert client["assistant_submissions"] == client["trial_submissions"] == []


def test_answer_requires_adoption_then_separate_trial_action(app, client):
    _ask(app)
    _ok(app)
    assert len(client["assistant_submissions"]) == 1
    assert client["trial_submissions"] == []
    assert ui._PROPOSAL_KEY not in app.session_state
    assert not any(item.label == "运行已采用方案" for item in app.button)
    _adopt(app)
    _ok(app)
    assert app.session_state[ui._PROPOSAL_KEY] == client["proposal"]
    assert client["trial_submissions"] == []
    _widget(app.button, "运行已采用方案").click().run()
    _ok(app)
    assert len(client["trial_submissions"]) == 1
    assert client["trial_submissions"][0]["proposal"] == client["proposal"]
    assert any("Project 运行完成" in row.value for row in app.success)
    assert [row.value for row in app.metric] == ["8", "20", "2.50 s"]
    app.run()
    assert len(client["assistant_submissions"]) == len(client["trial_submissions"]) == 1


def test_text_only_followup_does_not_replace_adopted_configuration(app, client):
    _ask(app)
    _adopt(app)
    previous = deepcopy(app.session_state[ui._PROPOSAL_KEY])
    client["proposal"] = None
    _ask(app, "先讨论下一轮偏好。")
    _ok(app)
    assert app.session_state[ui._PROPOSAL_KEY] == previous
    assert not any(item.label == "采用这个方案" for item in app.button)
    assert any("没有交付经校验的新方案" in item.value for item in app.caption)
    assert client["trial_submissions"] == []


def test_followup_sends_only_current_trial_identity_not_browser_metrics(app, client):
    _ask(app)
    _adopt(app)
    _widget(app.button, "运行已采用方案").click().run()
    _ask(app, "根据本轮运行，怎样改善平稳性？")
    _ok(app)
    payload = client["assistant_submissions"][-1]
    assert payload["trial"] == "b" * 32
    assert payload["proposal"] == client["proposal"]
    assert payload["history"]
    assert "metrics" not in payload and "result" not in payload


def test_adopting_new_proposal_marks_old_trial_and_excludes_old_evidence(app, client):
    _ask(app)
    _adopt(app)
    _widget(app.button, "运行已采用方案").click().run()
    client["proposal"] = _proposal(weight=0.03)
    _ask(app, "提高平稳偏好，但保留原目标。")
    _adopt(app)
    _ok(app)
    assert any("旧方案的运行记录" in item.value for item in app.warning)
    assert len(client["trial_submissions"]) == 1
    _ask(app, "请继续核对新方案。")
    assert client["assistant_submissions"][-1]["trial"] is None


def test_project_switch_clears_cross_project_configuration_and_history(app, client):
    _ask(app)
    _adopt(app)
    _widget(app.selectbox, "选择已有 Project").select("second").run()
    _ok(app)
    assert ui._PROPOSAL_KEY not in app.session_state
    assert ui._AI_JOB_KEY not in app.session_state
    assert ui._HISTORY_KEY not in app.session_state
    assert _widget(app.text_area, "这次想完成什么").value == ""
    assert client["trial_submissions"] == []


def test_wrong_project_proposal_cannot_be_adopted(app, client):
    client["proposal"] = _proposal("second")
    _ask(app)
    _ok(app)
    assert _widget(app.button, "采用这个方案").disabled
    assert any("项目身份" in item.value for item in app.warning)
    assert ui._PROPOSAL_KEY not in app.session_state


def test_unknown_ai_submit_retries_frozen_request_identity(app, client):
    client["assistant_submit_error"] = True
    _ask(app)
    _ok(app)
    first = deepcopy(client["assistant_submissions"][-1])
    assert ui._AI_INTENT_KEY in app.session_state
    assert ui._AI_JOB_KEY not in app.session_state
    client["assistant_submit_error"] = False
    _widget(app.button, "请 AI 读取项目并讨论").click().run()
    _ok(app)
    assert client["assistant_submissions"][-1] == first
    assert len(client["assistant_submissions"]) == 2


def test_unknown_trial_submit_retries_same_proposal_and_identity(app, client):
    _ask(app)
    _adopt(app)
    client["trial_submit_error"] = True
    _widget(app.button, "运行已采用方案").click().run()
    _ok(app)
    first = deepcopy(client["trial_submissions"][-1])
    assert ui._TRIAL_INTENT_KEY in app.session_state
    assert ui._TRIAL_JOB_KEY not in app.session_state
    client["trial_submit_error"] = False
    _widget(app.button, "运行已采用方案").click().run()
    _ok(app)
    assert client["trial_submissions"][-1] == first


def test_running_trial_disables_duplicate_run_and_completion_reenables(app, client):
    _ask(app)
    _adopt(app)
    client["trial_status"] = "running"
    _widget(app.button, "运行已采用方案").click().run()
    _ok(app)
    assert _widget(app.button, "运行已采用方案").disabled
    app.run()
    assert len(client["trial_submissions"]) == 1
    client["trial_status"] = "succeeded"
    _widget(app.button, "刷新项目运行").click().run()
    _ok(app)
    assert not _widget(app.button, "运行已采用方案").disabled


@pytest.mark.parametrize("status", ["failed", "timed_out"])
def test_failed_trial_is_not_presented_as_success(app, client, status):
    _ask(app)
    _adopt(app)
    client["trial_status"] = status
    _widget(app.button, "运行已采用方案").click().run()
    _ok(app)
    assert any("试跑超时" in row.value for row in app.error)
    assert not app.success
    _ask(app, "请根据失败记录解释下一步。")
    assert client["assistant_submissions"][-1]["trial"] == "b" * 32


def test_history_records_completed_answer_once_across_rerenders(app, client):
    _ask(app)
    _ok(app)
    history = deepcopy(app.session_state[ui._HISTORY_KEY])
    app.run()
    app.run()
    assert app.session_state[ui._HISTORY_KEY] == history
    assert len(history) == 2


def test_active_assistant_shows_bounded_tool_progress_without_source_contents(app, client):
    client["assistant_status"] = "running"
    client["progress"] = {"model_calls": 3, "tool_calls": 5, "tool_trace": [
        {"name": "project_read", "arguments": {"path": f"file-{i}.py"}, "ok": True,
         "result": {"content": "SOURCE_CONTENT_MUST_NOT_STAY_VISIBLE"}}
        for i in range(5)]}
    _ask(app)
    _ok(app)
    captions = "\n".join(row.value for row in app.caption)
    assert "模型请求 3 次" in captions and "已完成工具调用 5 次" in captions
    assert all(f"file-{i}.py" in captions for i in (2, 3, 4))
    assert all(f"file-{i}.py" not in captions for i in (0, 1))
    assert "SOURCE_CONTENT_MUST_NOT_STAY_VISIBLE" not in captions
    assert _widget(app.button, "请 AI 读取项目并讨论").disabled
    assert client["trial_submissions"] == []


def _archive(*, truncated=False):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("exports/plan.csv", "day,product_a\n1,1234\n")
    data = buffer.getvalue()
    return {"filename": "project-run-artifacts.zip", "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data), "base64": base64.b64encode(data).decode("ascii"),
            "truncated": truncated}


def test_verified_artifact_archive_is_downloadable_without_binary_in_visible_report(app, client):
    client["artifact_archive"] = _archive()
    _ask(app)
    _adopt(app)
    _widget(app.button, "运行已采用方案").click().run()
    _ok(app)
    labels = [row.proto.label for row in app.get("download_button")]
    assert "下载本次运行产物 ZIP" in labels
    assert "下载本轮项目运行记录" in labels
    assert any("SHA-256 已校验" in row.value for row in app.caption)
    assert not any('"base64"' in row.value for row in app.json)
    assert "base64" in app.session_state[ui._TRIAL_JOB_KEY]["result"]["artifact_archive"]


def test_partial_artifact_archive_is_labeled_without_losing_report_download(app, client):
    client["artifact_archive"] = _archive(truncated=True)
    _ask(app)
    _adopt(app)
    _widget(app.button, "运行已采用方案").click().run()
    _ok(app)
    assert len(app.get("download_button")) == 2
    assert any("仅包含本轮已核验的部分文件" in row.value for row in app.caption)


@pytest.mark.parametrize("field,value", [
    ("sha256", "0" * 64),
    ("size_bytes", 1),
    ("size_bytes", True),
    ("size_bytes", ui._MAX_ARCHIVE_BYTES + 1),
    ("base64", "not-base64!"),
    ("base64", "非ASCII"),
    ("filename", "../escape.zip"),
    ("filename", "report.zip\r\ninjected"),
    ("truncated", "yes"),
])
def test_invalid_artifact_archive_never_renders_download(app, client, field, value):
    archive = _archive()
    archive[field] = value
    client["artifact_archive"] = archive
    _ask(app)
    _adopt(app)
    _widget(app.button, "运行已采用方案").click().run()
    _ok(app)
    assert [row.proto.label for row in app.get("download_button")] == ["下载本轮项目运行记录"]
    assert any("未通过大小或摘要校验" in row.value for row in app.warning)
