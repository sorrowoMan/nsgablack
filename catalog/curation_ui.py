"""Read-only presentation of generated knowledge, separate from Catalog facts.

The deployment owns the immutable source-digest index. Browsers cannot choose
an index, database or model. Importing or rendering this module never calls AI.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import time
from typing import Any


INDEX_SCHEMA = "nsgablack.catalog.knowledge_sources/v1"
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_MAX_INDEX_BYTES = 4 * 1024 * 1024
_CACHE_SECONDS = 30


def enabled() -> bool:
    return os.environ.get("NSGABLACK_CATALOG_KNOWLEDGE_ENABLED", "").strip() == "1"


def _reader_fingerprint() -> str:
    values = tuple(os.environ.get(name, "") for name in (
        "NSGABLACK_CATALOG_DB_URL", "NSGABLACK_CATALOG_DB_PATH",
        "NSGABLACK_CATALOG_DB_MODE", "NSGABLACK_CATALOG_READER_CONFIG",
    ))
    return hashlib.sha256(repr(values).encode()).hexdigest()


def _read_index(path: str) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file() or source.stat().st_size > _MAX_INDEX_BYTES:
        raise ValueError("Knowledge index is missing or too large")
    index = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(index, dict) or index.get("schema") != INDEX_SCHEMA:
        raise ValueError("Knowledge index has an unsupported schema")
    entries = index.get("entries")
    if not isinstance(entries, dict) or not entries or any(
        not isinstance(key, str) or not key or not isinstance(digest, str) or not _DIGEST.fullmatch(digest)
        for key, digest in entries.items()
    ):
        raise ValueError("Knowledge index has invalid entry identities")
    profiles = index.get("profiles", {})
    if not isinstance(profiles, dict) or any(
        not isinstance(name, str) or not isinstance(keys, list)
        or any(not isinstance(key, str) or key not in entries for key in keys)
        for name, keys in profiles.items()
    ):
        raise ValueError("Knowledge index has invalid profile identities")
    prompt_version = index.get("prompt_version")
    if prompt_version is not None and (not isinstance(prompt_version, str) or not prompt_version.strip()):
        raise ValueError("Knowledge index has an invalid prompt version")
    return index


def _read_records() -> Sequence[Mapping[str, Any]]:
    from .curation_store import resolve_knowledge_store

    return resolve_knowledge_store(readonly=True).list_latest()


@lru_cache(maxsize=8)
def _load_snapshot(index_path: str, index_revision: tuple[int, int], reader_fingerprint: str,
                   cache_epoch: int) -> dict[str, Any]:
    # Cache arguments bind source and deployment configuration without retaining
    # a database URL in a public cache key or constructing per-component readers.
    del index_revision, reader_fingerprint, cache_epoch
    try:
        index = _read_index(index_path)
        records: dict[str, dict[str, Any]] = {}
        for value in _read_records():
            if not isinstance(value, Mapping):
                raise ValueError("Knowledge storage returned an invalid record")
            key = value.get("entry_key")
            if not isinstance(key, str) or not key or key in records:
                raise ValueError("Knowledge storage returned duplicate or invalid identities")
            records[key] = dict(value)
        return {"enabled": True, "available": True, "index": index, "records": records,
                "validated": {key: _note_record_valid(record) for key, record in records.items()}}
    except Exception as exc:
        # Driver messages may include credentials or private deployment paths.
        return {"enabled": True, "available": False, "error_type": type(exc).__name__}


def knowledge_snapshot() -> dict[str, Any]:
    if not enabled():
        return {"enabled": False, "available": False}
    path = os.environ.get("NSGABLACK_CATALOG_KNOWLEDGE_INDEX", "").strip()
    try:
        stat = Path(path).stat() if path else None
        revision = (stat.st_mtime_ns, stat.st_size) if stat else (0, 0)
    except OSError:
        revision = (0, 0)
    return _load_snapshot(path, revision, _reader_fingerprint(), int(time.monotonic() // _CACHE_SECONDS))


def _note_record_valid(record: Mapping[str, Any]) -> bool:
    note = record.get("note")
    evidence = record.get("evidence")
    if not isinstance(note, Mapping) or not isinstance(evidence, (list, tuple)):
        return False
    for name in ("summary", "inputs_outputs"):
        if not isinstance(note.get(name), str):
            return False
    for name in ("use_when", "assembly_steps", "pitfalls", "related_keys", "missing_information", "evidence_ids"):
        values = note.get(name)
        if not isinstance(values, (list, tuple)) or len(values) > 64 or any(not isinstance(value, str) for value in values):
            return False
    source_ids = {item.get("id") for item in evidence
                  if isinstance(item, Mapping) and isinstance(item.get("id"), str) and _safe_evidence(item)}
    tutorial = note.get("tutorial")
    if str(record.get("prompt_version", "")).startswith("catalog-tutorial-") and tutorial is None:
        return False
    if tutorial is not None:
        try:
            from .curation import validate_tutorial
            validate_tutorial(tutorial, evidence_ids=source_ids, allow_reference=True)
        except (ValueError, TypeError):
            return False
    if str(record.get("prompt_version", "")).startswith("catalog-tutorial-reviewed-"):
        review = note.get("tutorial_review")
        if not isinstance(review, Mapping) or review.get("decision") != "publish":
            return False
        try:
            from .tutorial_review import validate_review
            payload = {key: review[key] for key in ("decision", "issues", "checks", "evidence_ids")}
            checked = validate_review(payload, evidence_ids=source_ids)
            if checked["version"] != review.get("version"):
                return False
        except (KeyError, ValueError, TypeError):
            return False
    return bool(note["evidence_ids"]) and set(note["evidence_ids"]) <= source_ids


def entry_knowledge(entry_key: str, snapshot: Mapping[str, Any] | None = None) -> dict[str, Any]:
    state = knowledge_snapshot() if snapshot is None else snapshot
    if not state.get("enabled"):
        return {"status": "disabled"}
    if not state.get("available"):
        return {"status": "unavailable", "error_type": state.get("error_type", "KnowledgeStoreError")}
    expected = state["index"]["entries"].get(entry_key)
    if expected is None:
        return {"status": "unindexed"}
    record = state["records"].get(entry_key)
    if record is None:
        return {"status": "missing"}
    if record.get("source_digest") != expected:
        return {"status": "stale"}
    current_prompt = state["index"].get("prompt_version")
    if current_prompt is not None and record.get("prompt_version") != current_prompt:
        return {"status": "stale"}
    validated = state.get("validated")
    valid = validated.get(entry_key, False) if isinstance(validated, Mapping) else _note_record_valid(record)
    if not valid:
        return {"status": "invalid"}
    return {"status": "current", "record": record}


def render_status(st: Any, *, profile: str = "default") -> None:
    snapshot = knowledge_snapshot()
    if not snapshot.get("enabled"):
        return
    # Streamlit expanders do not defer their body. Reuse the same cached
    # read-only snapshot rather than introducing a second read or refresh.
    with st.expander("资料维护详情", expanded=False):
        if not snapshot.get("available"):
            st.caption(f"AI 说明缓存暂不可读（{snapshot.get('error_type', 'KnowledgeStoreError')}）")
            return
        index = snapshot["index"]
        states = {key: entry_knowledge(key, snapshot)["status"] for key in index["entries"]}
        profiles = index.get("profiles", {})
        if not isinstance(profiles, Mapping) or profile not in profiles:
            st.caption("当前目录范围未在资料索引登记，暂不汇总此范围的 AI 缓存。")
        else:
            keys = profiles[profile]
            if (not isinstance(keys, (list, tuple)) or any(not isinstance(key, str) for key in keys)
                    or len(set(keys)) != len(keys)):
                st.caption("当前目录范围的资料索引无效，暂不汇总 AI 缓存。")
            else:
                counts: dict[str, int] = {}
                for key in keys:
                    status = states[key] if key in states else entry_knowledge(key, snapshot)["status"]
                    counts[status] = counts.get(status, 0) + 1
                summary = (f"AI 缓存 · 当前目录范围 {len(keys)} 项：可复用 {counts.get('current', 0)} · "
                           f"已过期 {counts.get('stale', 0)} · 未生成 {counts.get('missing', 0)} · "
                           f"校验未通过 {counts.get('invalid', 0)}")
                if counts.get("unindexed"):
                    summary += f" · 未登记来源 {counts['unindexed']}"
                known = {"current", "stale", "missing", "invalid", "unindexed"}
                unknown = sum(count for status, count in counts.items() if status not in known)
                if unknown:
                    summary += f" · 状态未确定 {unknown}"
                st.caption(summary)
                if not keys:
                    st.caption("当前目录范围为空，没有需要统计的 AI 缓存。")
        st.caption("这些状态只说明旧 AI 记录的可复用性，不代表源码用法缺失；也不是组件运行验收。")
        st.caption("浏览目录或刷新页面不会启动 AI 整理。")
        from .curation_progress import read_progress, status_message
        progress = read_progress(dict(index["entries"]), prompt_version=index.get("prompt_version"))
        actual_current = sum(status == "current" for status in states.values())
        if progress.get("available") and progress["current"] != actual_current:
            progress = {**progress, "current": actual_current, "counts_syncing": True}
            if progress["status"] not in {"paused", "user_paused"}:
                progress["status"] = "syncing"
        st.caption("AI 缓存维护记录：" + status_message(progress))
        if progress.get("available"):
            st.caption("后台最近检查：" + progress["checked_at"])


def _render_values(st: Any, title: str, values: Sequence[str], *, numbered: bool = False) -> None:
    if not values:
        return
    st.markdown(f"**{title}**")
    for index, value in enumerate(values, start=1):
        # Generated prose never receives unsafe HTML privileges or execution.
        st.markdown(f"{index}. {value}" if numbered else f"- {value}", unsafe_allow_html=False)


def _safe_evidence(item: Mapping[str, Any]) -> bool:
    path = item.get("path")
    start, end = item.get("start_line"), item.get("end_line")
    text, digest = item.get("text"), item.get("sha256")
    if not isinstance(path, str) or "\\" in path or ":" in path:
        return False
    parts = PurePosixPath(path)
    return (not parts.is_absolute() and ".." not in parts.parts
            and isinstance(start, int) and not isinstance(start, bool) and start > 0
            and isinstance(end, int) and not isinstance(end, bool) and end >= start
            and isinstance(text, str) and bool(text) and len(text.splitlines()) == end - start + 1
            and isinstance(digest, str) and _DIGEST.fullmatch(digest) is not None
            and hashlib.sha256(text.encode("utf-8")).hexdigest() == digest)


def render_tutorial(st: Any, *, entry_key: str, profile: str = "default",
                    include_baseline: bool = True) -> bool:
    """Show source-bound detailed teaching from the existing knowledge DB."""
    snapshot = knowledge_snapshot()
    state = entry_knowledge(entry_key, snapshot)
    if state.get("status") != "current":
        return False
    allowed = snapshot["index"].get("profiles", {}).get(profile, snapshot["index"]["entries"])
    if entry_key not in allowed:
        return False
    record = state["record"]
    raw = record["note"].get("tutorial")
    if raw is None:
        return False
    from .curation import validate_tutorial
    ids = {item["id"] for item in record["evidence"] if _safe_evidence(item)}
    try:
        guide = validate_tutorial(raw, evidence_ids=ids, allow_reference=True)
    except (ValueError, TypeError):
        return False
    from .examples_ui import _list
    if include_baseline:
        st.caption("AI依据本版源码整理的用法；下面的代码尚未执行。")
        st.markdown("**可以用它做什么** · " + guide["scenario"], unsafe_allow_html=False)
        _list(st, "先准备什么", guide["preparation"])
        st.markdown("**代码放在哪** · " + guide["placement"], unsafe_allow_html=False)
        if guide["code"]:
            st.code(guide["code"], language=guide["language"], wrap_lines=True)
        _list(st, "接上后怎样运行", guide["execution_flow"], numbered=True)
        _list(st, "怎样检查结果", guide["result_checks"])
    else:
        st.caption("下方变化用法由AI依据当前源码整理，尚未执行；上面的正式基础用法保留。")
    if guide["extensions"]:
        st.markdown("**还能怎样改**", unsafe_allow_html=False)
        for variation in guide["extensions"]:
            st.markdown("**" + variation["title"] + "** · " + variation["purpose"], unsafe_allow_html=False)
            with st.expander("查看改法 · " + variation["title"], expanded=False):
                st.markdown("**改在哪里** · " + variation["placement"], unsafe_allow_html=False)
                if variation["code"]:
                    st.code(variation["code"], language=variation["language"], wrap_lines=True)
                st.markdown("**会发生什么变化** · " + variation["effect"], unsafe_allow_html=False)
                _list(st, "适用条件", variation["limits"])
    with st.expander("AI用法的源码依据", expanded=False):
        review = record["note"].get("tutorial_review")
        if isinstance(review, Mapping) and review.get("decision") == "publish":
            st.caption("另一次AI源码复核已检查接线、运行过程与变体；仍不是实际运行验收。")
            _list(st, "源码复核内容", review["checks"])
        selected = set(guide["evidence_ids"])
        selected.update(identifier for variation in guide["extensions"] for identifier in variation["evidence_ids"])
        for item in record["evidence"]:
            if item.get("id") in selected and _safe_evidence(item):
                st.caption(f"{item['path']}:{item['start_line']}-{item['end_line']}")
                st.code(item["text"], language="python" if item["path"].endswith(".py") else "text", wrap_lines=True)
    return True


def render_note(st: Any, *, entry_key: str, profile: str = "default",
                on_navigate: Callable[..., Any] | None = None,
                navigation_kwargs: Mapping[str, Any] | None = None) -> None:
    snapshot = knowledge_snapshot()
    state = entry_knowledge(entry_key, snapshot)
    if state["status"] == "disabled":
        return
    st.markdown("### AI 使用说明")
    if state["status"] == "unavailable":
        st.info(f"整理结果暂不可用（{state.get('error_type', 'KnowledgeStoreError')}）；组件原始声明仍可查看。")
        return
    messages = {
        "missing": "此组件尚无匹配当前版本的 AI 说明缓存；请查看本组件的源码用法与原始契约。",
        "unindexed": "此组件未纳入当前 AI 缓存索引；源码用法与原始契约仍可查看。",
        "stale": "此组件的旧 AI 说明缓存已过期，未作为当前用法展示；请查看当前源码用法。",
        "invalid": "此组件的整理记录格式需要重新检查；原始声明仍可查看。",
    }
    if state["status"] != "current":
        st.info(messages[state["status"]])
        return
    record = state["record"]
    note = record["note"]
    st.caption("基于当前源码生成的解释性说明；未进行运行验收，不替代原始接口契约。")
    st.markdown(note["summary"], unsafe_allow_html=False)
    _render_values(st, "适合什么时候用", note["use_when"])
    if note["inputs_outputs"]:
        st.markdown("**输入与输出**")
        st.markdown(note["inputs_outputs"], unsafe_allow_html=False)
    _render_values(st, "装配思路", note["assembly_steps"], numbered=True)
    _render_values(st, "需要注意", note["pitfalls"])
    _render_values(st, "仍缺少的信息", note["missing_information"])
    allowed_keys = snapshot["index"].get("profiles", {}).get(profile, snapshot["index"]["entries"])
    related = list(dict.fromkeys(key for key in note["related_keys"] if key in allowed_keys and key != entry_key))
    if related:
        with st.expander("相关组件", expanded=False):
            for key in related:
                if on_navigate is None:
                    st.code(key, language=None)
                else:
                    st.button(key, key=f"catalog_ai::related::{entry_key}::{key}", width="stretch",
                              on_click=on_navigate, kwargs={**dict(navigation_kwargs or {}), "target_key": key})
    selected_ids = set(note["evidence_ids"])
    with st.expander("依据与整理版本", expanded=False):
        st.caption(f"模型：{record.get('model', '')} · 时间：{record.get('generated_at', '')}")
        st.caption(f"整理规则：{record.get('prompt_version', '')} · 源码摘要：{record.get('source_digest', '')[:12]}")
        for item in record["evidence"]:
            if not isinstance(item, Mapping) or item.get("id") not in selected_ids or not _safe_evidence(item):
                continue
            st.caption(f"{item['path']}:{item['start_line']}-{item['end_line']}")
            if isinstance(item.get("text"), str) and item["text"]:
                st.code(item["text"][:16000], language="python" if item["path"].endswith(".py") else None)


__all__ = ["enabled", "knowledge_snapshot", "entry_knowledge", "render_status", "render_note", "render_tutorial"]
