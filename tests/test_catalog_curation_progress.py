import json
from datetime import datetime, timezone

import pytest

from nsgablack.catalog.curation_progress import ENV, SCHEMA, read_progress, source_identity, status_message


@pytest.fixture
def progress_file(tmp_path, monkeypatch):
    entries = {"tool.pool": "a" * 64}
    value = {"schema": SCHEMA, "source_index_sha256": source_identity(entries),
             "total": 1, "current": 0, "daily_limit": 100, "reserved_today": 100,
             "status": "daily_limit", "checked_at": "2026-10-23T01:00:00Z"}
    path = tmp_path / "progress.json"
    monkeypatch.setenv(ENV, str(path))
    return entries, value, path


def test_limit_is_explained_and_private_fields_are_never_returned(progress_file):
    entries, value, path = progress_file
    value["untrusted"] = "do not display this"
    path.write_text(json.dumps(value))
    state = read_progress(entries)
    assert "每日 100" in status_message(state)
    assert state["checked_at"] == "10-23 09:00 UTC+08:00"
    assert "untrusted" not in state


@pytest.mark.parametrize("change", [{"source_index_sha256": "b" * 64}, {"total": 2}, {"current": True},
                                   {"current": 2}, {"checked_at": "2026-10-23T01:00:00"}, {"status": "<script>"}])
def test_wrong_release_and_malformed_status_are_not_presented_as_current(progress_file, change):
    entries, value, path = progress_file
    value.update(change)
    path.write_text(json.dumps(value))
    assert not read_progress(entries)["available"]


def test_completion_and_catchup_override_regular_limit_message(progress_file):
    entries, value, path = progress_file
    value["status"] = "catching_up"
    value["checked_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(value))
    assert "正在补齐" in status_message(read_progress(entries))
    value["current"] = 1
    path.write_text(json.dumps(value))
    message = status_message(read_progress(entries))
    assert "已全部整理" in message and "自动检查" not in message


def test_old_running_state_and_wrong_prompt_cannot_claim_current_work(progress_file):
    entries, value, path = progress_file
    value.update(status="running", checked_at="2020-01-01T00:00:00Z", prompt_version="v3")
    path.write_text(json.dumps(value))
    assert "已过期" in status_message(read_progress(entries, prompt_version="v3"))
    assert not read_progress(entries, prompt_version="v4")["available"]


@pytest.mark.parametrize("status", ["paused", "user_paused"])
@pytest.mark.parametrize("current", [0, 1])
def test_explicit_pause_precedes_completion_quota_and_next_time(progress_file, status, current):
    entries, value, path = progress_file
    value.update(status=status, current=current, next_eligible_at=2000000000)
    path.write_text(json.dumps(value))
    state = read_progress(entries)
    state["counts_syncing"] = True
    message = status_message(state)
    assert "已暂停" in message and "不会自动恢复" in message
    assert "对账" in message and "暂停状态不变" in message
    assert all(text not in message for text in ("模型服务", "已全部整理", "可处理时间", "每日"))


@pytest.mark.parametrize("status", ["pending", "idle", "unknown_state"])
def test_unknown_status_and_old_quota_counters_do_not_assert_automatic_work(progress_file, status):
    entries, value, path = progress_file
    value.update(status=status, next_eligible_at=2000000000)
    path.write_text(json.dumps(value))
    message = status_message(read_progress(entries))
    assert "状态尚未确认" in message and "不会启动 AI" in message
    assert all(text not in message for text in ("自动整理已启用", "后台分批", "每日", "可处理时间"))


@pytest.mark.parametrize("state", [{"available": False}, {"available": False, "stale": True}])
def test_missing_progress_cannot_assert_a_running_or_automatic_job(state):
    message = status_message(state)
    assert all(text not in message for text in ("自动整理已启用", "后台独立运行", "自动检查"))
