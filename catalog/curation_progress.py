"""Read a deployment-owned, sanitized progress snapshot; never start AI work."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re

SCHEMA = "nsgablack.catalog.curation_progress/v1"
ENV = "NSGABLACK_CATALOG_PROGRESS_PATH"
_TZ = timezone(timedelta(hours=8))


def source_identity(entries: dict) -> str:
    return hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_progress(entries: dict, *, prompt_version: str | None = None) -> dict:
    path = os.environ.get(ENV, "").strip()
    if not path:
        return {"available": False}
    try:
        file = Path(path)
        if not file.is_file() or file.stat().st_size > 32768:
            return {"available": False}
        value = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema") != SCHEMA:
            return {"available": False}
        if value.get("source_index_sha256") != source_identity(entries):
            return {"available": False, "stale": True}
        if prompt_version is not None and value.get("prompt_version") != prompt_version:
            return {"available": False, "stale": True}
        for key in ("total", "current", "daily_limit", "reserved_today"):
            number = value.get(key)
            if type(number) is not int or not 0 <= number <= 100000:
                return {"available": False}
        if value["total"] != len(entries) or value["current"] > value["total"]:
            return {"available": False}
        checked = datetime.fromisoformat(value["checked_at"].replace("Z", "+00:00"))
        if checked.tzinfo is None:
            return {"available": False}
        status = value.get("status")
        if not isinstance(status, str) or not re.fullmatch(r"[a-z_]{1,40}", status):
            return {"available": False}
        if status in {"catching_up", "draining", "reserved", "running"} and (datetime.now(timezone.utc) - checked).total_seconds() > 1800:
            status = "outdated"
        result = {key: value[key] for key in ("total", "current", "daily_limit", "reserved_today", "status")}
        result.update(available=True, checked_at=checked.astimezone(_TZ).strftime("%m-%d %H:%M UTC+08:00"))
        result["status"] = status
        next_at = value.get("next_eligible_at")
        if isinstance(next_at, (float, int)) and not isinstance(next_at, bool) and next_at > 0:
            result["next_at"] = datetime.fromtimestamp(next_at, _TZ).strftime("%m-%d %H:%M UTC+08:00")
        return result
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        return {"available": False}


def status_message(progress: dict) -> str:
    if not progress.get("available"):
        return ("后台进度属于旧发布，当前任务状态尚未确认。" if progress.get("stale")
                else "后台状态暂不可用；上方数量来自当前数据库，不能据此确认任务已启动。")
    status = progress["status"]
    if status in {"paused", "user_paused"}:
        message = "AI 资料整理已暂停，不会自动恢复；继续处理需明确启动维护任务。"
        if progress.get("counts_syncing"):
            message += " 资料数量正在对账，暂停状态不变。"
        return message
    if status == "outdated":
        message = "后台运行状态已过期，等待新的检查；不代表仍在整理。"
    elif status == "syncing":
        message = "后台进度与当前资料正在对账，请稍后刷新。"
    elif progress["current"] == progress["total"]:
        message = "当前发布资料已全部整理；后续处理由维护计划决定。"
    elif status in {"catching_up", "draining", "reserved", "running"}:
        message = "正在补齐当前发布的待整理资料。"
    elif status in {"circuit_open", "circuit_breaker"}:
        message = "模型服务暂停，后台保留待办并等待恢复。"
    elif status in {"backoff", "retry_wait", "partial", "failed"}:
        message = "部分资料需重试，后台保留待办与退避状态。"
    elif status == "awaiting_evidence":
        message = "剩余组件缺少可用源码证据，需补齐资料后继续整理。"
    elif status in {"daily_limit", "quota_wait"}:
        message = f"后台任务达到配置的每日 {progress['daily_limit']} 项处理上限；后续处理由维护计划决定。"
    else:
        message = "后台任务状态尚未确认；浏览目录或刷新页面不会启动 AI 整理。"
    if progress.get("next_at") and status in {"backoff", "retry_wait", "daily_limit", "quota_wait"}:
        message += " 记录的最早可处理时间：" + progress["next_at"] + "。"
    return message
