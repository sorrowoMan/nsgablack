"""Read-only component reference over already published Catalog artifacts.

The workbench does not need a Catalog DB credential or a component import to
show usage. The Catalog image already contains materialized entry packets and
source-checked example excerpts. This module reads those immutable records;
it never calls a registry factory, ``entry.load`` or a model provider.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re

from nsgablack.catalog.usage_learning import (select_documentation_guide,
                                             snippet_parts, source_link_text)


_KEY = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,199}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_PROFILES = frozenset({"default", "framework-core"})
_ROOT_ENV = "NSGABLACK_WORKSPACE_REFERENCE_ROOT"
_POPULAR = ("adapter.nsga2", "adapter.vns", "adapter.moead", "adapter.search_plan",
            "tool.pool", "tool.pool_task_spec", "tool.subpools")


def _strings(value):
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    if isinstance(value, (list, tuple)):
        return tuple(item for item in value if isinstance(item, str) and item.strip())
    return ()


def _catalog(row):
    contract = row.get("contract")
    declared = contract.get("catalog") if isinstance(contract, Mapping) else None
    return declared if isinstance(declared, Mapping) else {}


class ReferenceSource:
    """Detached published records, also injectable for local UI tests.

    ``entries`` are materialized mappings, never live component objects.
    Profiles are supplied by the published Catalog index, not inferred here.
    """
    def __init__(self, entries=(), examples=None, *, profiles=None,
                 source_note="已提供的 Catalog 资料；只读，不执行组件。",
                 available=True, publication_digest=None):
        records = entries.values() if isinstance(entries, Mapping) else entries
        self.entries = {}
        for row in records:
            if not isinstance(row, Mapping) or not _KEY.fullmatch(str(row.get("key", ""))):
                raise ValueError("组件资料必须是已发布的记录。")
            key = row["key"]
            if key in self.entries:
                raise ValueError("组件资料含重复身份。")
            self.entries[key] = deepcopy(dict(row))
        if profiles is None:
            profiles = {"default": list(self.entries)}
        self.profiles = {}
        for name, keys in profiles.items():
            if name not in _PROFILES or not isinstance(keys, (list, tuple)) or any(key not in self.entries for key in keys):
                raise ValueError("组件资料口径不匹配。")
            self.profiles[name] = frozenset(keys)
        self.examples = deepcopy(examples or {"entries": {}, "examples": {}})
        self.source_note = str(source_note)
        self.available = bool(available)
        self.publication_digest = publication_digest
        self._search_text = {}
        for key, row in self.entries.items():
            catalog = _catalog(row)
            examples = self.examples.get("examples", {})
            linked = [examples.get(identifier, {}) for identifier in self.examples.get("entries", {}).get(key, ())]
            guide_text = [str(snippet.get("text", "")) for example in linked
                          if isinstance(example, Mapping) and key in example.get("component_keys", ())
                          for snippet in example.get("snippets", ()) if isinstance(snippet, Mapping)]
            values = [key, row.get("title", ""), row.get("summary", ""), row.get("import_path", ""),
                      *_strings(row.get("tags")), *_strings(row.get("config_keys")),
                      *_strings(row.get("minimal_wiring")), *guide_text,
                      *_strings(row.get("use_when")), *_strings(catalog.get("concepts")),
                      *_strings(catalog.get("operations"))]
            self._search_text[key] = " ".join(str(value) for value in values).casefold()


def _read_json(path, maximum):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("组件发布资料缺失或超出读取范围。")
    raw = path.read_bytes()
    if len(raw) > maximum:
        raise ValueError("组件发布资料超出读取范围。")
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("组件发布资料存在重复字段。")
            value[key] = item
        return value
    def invalid(_):
        raise ValueError("组件发布资料含非有限数字。")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid), raw


def load_reference_source(packets_path, index_path, examples_path):
    """Read operator-selected public artifacts; no paths come from UI queries."""
    packets, raw = _read_json(packets_path, 32 * 1024 * 1024)
    index, _ = _read_json(index_path, 2 * 1024 * 1024)
    if (not isinstance(packets, Mapping) or packets.get("schema") != "nsgablack.catalog.knowledge_packets/v1"
            or not isinstance(packets.get("packets"), Mapping)
            or not isinstance(index, Mapping) or index.get("schema") != "nsgablack.catalog.knowledge_sources/v1"
            or index.get("packets_sha256") != hashlib.sha256(raw).hexdigest()):
        raise ValueError("组件发布资料摘要或格式不匹配。")
    records, digests = [], {}
    for key, packet in packets["packets"].items():
        if (not isinstance(packet, Mapping) or not isinstance(packet.get("entry"), Mapping)
                or packet["entry"].get("key") != key
                or not _HEX.fullmatch(str(packet.get("source_digest", "")))):
            raise ValueError("组件发布资料身份不匹配。")
        records.append(packet["entry"])
        digests[key] = packet["source_digest"]
    profiles = index.get("profiles")
    if (index.get("entries") != digests or not isinstance(profiles, Mapping)
            or set(profiles.get("default", ())) != set(digests)):
        raise ValueError("组件发布资料口径不匹配。")
    examples, _ = _read_json(examples_path, 16 * 1024 * 1024)
    from nsgablack.catalog.examples import validate_example_index
    examples = validate_example_index(examples)
    if set(examples["entries"]) != set(digests):
        raise ValueError("组件用法与发布目录不匹配。")
    return ReferenceSource(records, examples, profiles=profiles,
        publication_digest=examples.get("publication_digest"),
        source_note=f"当前镜像随附的已发布 Catalog：{len(records)} 项；源码说明与实际运行证据分别记录。")


@lru_cache(maxsize=2)
def _cached_source(root, signature):
    del signature
    base = Path(root)
    try:
        return load_reference_source(base / "knowledge-packets.json", base / "knowledge-sources.json",
                                     base / "examples.json")
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        return ReferenceSource(available=False,
            source_note="当前环境没有可核对的完整 Catalog 发布资料；尚未连接组件速查。")


def reference_source():
    root = Path(os.environ.get(_ROOT_ENV, "/opt/catalog"))
    signature = []
    for name in ("knowledge-packets.json", "knowledge-sources.json", "examples.json"):
        try:
            stat = (root / name).stat()
            signature.append((stat.st_mtime_ns, stat.st_size))
        except OSError:
            signature.append(None)
    return _cached_source(str(root), tuple(signature))


def _source(value):
    if value is None:
        return reference_source()
    if not isinstance(value, ReferenceSource):
        raise TypeError("source must be ReferenceSource")
    return value


def _profile_keys(source, profile):
    if profile not in _PROFILES:
        raise ValueError("未知 Catalog 口径。")
    return source.profiles.get(profile, frozenset())


def _brief(row):
    return {key: str(row.get(key) or "") for key in ("key", "title", "kind", "summary")}


def reference_search(query="", kind="all", limit=12, *, source=None, profile="default"):
    """Search declared names, roles and usage concepts without imports."""
    if not isinstance(query, str) or len(query) > 300 or not isinstance(kind, str) or len(kind) > 60:
        raise ValueError("组件搜索输入过长或格式无效。")
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("组件结果数量应在 1 到 50 之间。")
    source = _source(source)
    keys = _profile_keys(source, profile)
    tokens = query.casefold().split()
    rows = [row for key, row in source.entries.items() if key in keys
            and (kind in {"all", ""} or row.get("kind") == kind)
            and all(token in source._search_text[key] for token in tokens)]
    def rank(row):
        key, title = row["key"].casefold(), str(row.get("title", "")).casefold()
        text = query.strip().casefold()
        priority = 0 if text and text in {key, title} else 1 if text and (text in key or text in title) else 2
        popular = _POPULAR.index(key) if not tokens and key in _POPULAR else len(_POPULAR)
        return priority, popular, key
    rows.sort(key=rank)
    return {"available": source.available, "items": [_brief(row) for row in rows[:limit]],
            "total": len(rows), "catalog_total": len(keys), "source_note": source.source_note,
            "profile": profile}


def _example_records(key, source):
    index = source.examples
    identifiers = index.get("entries", {}).get(key, ())
    records = [index.get("examples", {}).get(identifier) for identifier in identifiers]
    records = [row for row in records if isinstance(row, Mapping) and key in row.get("component_keys", ())]
    guide = select_documentation_guide(records)
    rank = {"executed": 0, "source_checked": 1, "unverified": 2}
    ordered = sorted(records, key=lambda row: (row is not guide,
        0 if row.get("binding") == "focused" else 1,
        rank.get(row.get("verification", {}).get("status"), 3)))
    return ordered


def _blocks(snippet, title):
    original = str(snippet.get("text", "")).replace("\r\n", "\n")
    cursor, result = 0, []
    for kind, text, language in snippet_parts(snippet):
        offset = original.find(text, cursor)
        if offset >= 0:
            cursor = offset + len(text)
        if kind != "code" or not text.strip():
            continue
        start = snippet.get("start_line")
        line = start + original[:offset].count("\n") if type(start) is int and offset >= 0 else start
        result.append({"title": title, "language": language or "text", "code": text,
                       "source_path": str(snippet.get("path", "")), "start_line": line})
    return result


def reference_detail(key, *, source=None, profile="default"):
    """Return exact published prose/code; missing fields stay explicitly absent."""
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise ValueError("组件身份格式无效。")
    source = _source(source)
    if not source.available or key not in _profile_keys(source, profile):
        return None
    row = source.entries[key]
    records = _example_records(key, source)
    usage, blocks, parameters, evidence, seen_code, seen_parameter = [], [], [], [], set(), set()
    # A focused component guide is sufficient. Keep its variants, and one real
    # Project/Case source if present, without repeating every book preface.
    chosen = records[:1]
    runnable = next((record for record in records if record.get("kind") in {"project", "case"}
                     and record.get("binding") == "focused" and record not in chosen), None)
    if runnable is not None:
        chosen.append(runnable)
    for example in chosen:
        state = str(example.get("verification", {}).get("status", "unverified"))
        evidence.append({"title": str(example.get("title", "")), "status": state,
                         "run_command": str(example.get("run_command", ""))})
        for snippet in example.get("snippets", ()):
            if not isinstance(snippet, Mapping) or not isinstance(snippet.get("text"), str):
                continue
            path = str(snippet.get("path", ""))
            if path.lower().endswith((".md", ".rst")):
                usage.append(source_link_text(snippet["text"], path))
            for block in _blocks(snippet, str(example.get("title", "用法片段"))):
                identity = (block["language"], block["code"])
                if identity not in seen_code:
                    blocks.append(block); seen_code.add(identity)
        for parameter in example.get("parameters", ()):
            if isinstance(parameter, Mapping) and all(isinstance(parameter.get(name), str)
                                                     for name in ("name", "value", "meaning")):
                identity = tuple(parameter[name] for name in ("name", "value", "meaning"))
                if identity not in seen_parameter:
                    parameters.append(dict(parameter)); seen_parameter.add(identity)
    if not blocks and _strings(row.get("minimal_wiring")):
        blocks.append({"title": "目录声明的最小装配片段", "language": "python",
            "code": "\n".join(_strings(row["minimal_wiring"])), "source_path": "", "start_line": None})
    declared = _catalog(row)
    relations = []
    required = _strings(row.get("required_companions"))
    for target in dict.fromkeys((*required, *_strings(row.get("companions")))):
        if target == key:
            continue
        entry = source.entries.get(target)
        relations.append({"key": target, "title": str((entry or {}).get("title", target)),
                          "kind": str((entry or {}).get("kind", "")), "available": entry is not None,
                          "reason": "必需配套（目录声明）" if target in required else "关联组件（目录声明）"})
    statuses = {item["status"] for item in evidence}
    note = ("含当前发布的运行收据；仅对应列出的示例和环境。" if "executed" in statuses else
            "用法源码已核对，未声明当前版本运行成功。" if "source_checked" in statuses else
            "目录声明或未验证片段；复制代码不代表已经运行。")
    return {**_brief(row), "import_path": str(row.get("import_path", "")),
            "usage_markdown": "\n\n---\n\n".join(usage), "code_blocks": blocks,
            "parameters": parameters, "relations": relations, "evidence_note": note,
            "evidence": evidence, "operations": list(_strings(declared.get("operations"))),
            "boundaries": list(_strings(declared.get("boundaries"))),
            "config_keys": list(_strings(row.get("config_keys"))),
            "use_when": list(_strings(row.get("use_when"))),
            "source_note": source.source_note, "publication_digest": source.publication_digest}
