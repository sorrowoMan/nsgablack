"""Follow explicit tutorial links within the current Catalog, without imports.

These are reading destinations, not dependency or compatibility relations. Only
links in the selected, verified guide and destinations in the caller's current
Catalog scope are eligible. No source file is read or component constructed.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import posixpath
import re
from typing import Any
from urllib.parse import unquote

from .usage_learning import select_documentation_guide, snippet_parts


_LINK = re.compile(r"(?<!!)\[([^\]\n]+)\]\(([^)\n]+)\)")
_FRAMEWORKS = {"nsgablack", "blackbase", "mlblack"}


def _destination(value: str, source: str) -> tuple[str, str] | None:
    value = value.strip()
    target = value[1:value.find(">")] if value.startswith("<") and ">" in value else value.split()[0] if value else ""
    if not target or target.startswith("//") or re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", target):
        return None
    target = unquote(target)
    if "\\" in target or "?" in target or any(ord(char) < 32 for char in target):
        return None
    path, _, anchor = target.partition("#")
    if path.startswith("/"):
        path = posixpath.join(source.split("/", 1)[0], path.lstrip("/"))
    else:
        path = posixpath.normpath(posixpath.join(posixpath.dirname(source), path)) if path else source
    if path.split("/", 1)[0] not in _FRAMEWORKS or not path.endswith(".md"):
        return None
    return path, anchor


def _slug(text: str) -> str:
    # Match explicit section IDs and the ordinary GitHub heading convention;
    # never turn an arbitrary word or a similar title into a component match.
    text = re.sub(r"`|\*", "", text).strip().lower()
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def _anchors(snippet: Mapping[str, Any]) -> set[str]:
    anchors = set()
    for kind, text, _ in snippet_parts(snippet):
        if kind != "text":
            continue
        for heading in re.findall(r"(?m)^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", text):
            anchors.add(_slug(heading))
            # Source manifests use exact component keys as section identities.
            first = re.match(r"`?([A-Za-z0-9_.-]+)`?(?:\s|$)", heading)
            if first:
                anchors.add(first[1])
    return anchors


def _verified(example: Mapping[str, Any]) -> bool:
    return (example.get("binding") == "focused" and example.get("kind") == "documentation"
            and example.get("verification", {}).get("status") in {"source_checked", "executed"}
            and not example.get("issues") and not example.get("_index_issues"))


def documentation_reference_groups(index: Mapping[str, Any], entry_key: str) -> tuple[dict[str, Any], ...]:
    """Resolve authored document links to exact indexed component sections."""
    records = index.get("examples", {})
    invalid = {item.get("example_id") for item in index.get("issues", ())}
    owned = [records[identifier] for identifier in index.get("entries", {}).get(entry_key, ())
             if identifier in records and identifier not in invalid and _verified(records[identifier])]
    selected = select_documentation_guide(owned)
    if selected is None:
        return ()
    links = {}
    for snippet in selected.get("snippets", ()):
        if snippet.get("complete") is not True:
            continue
        for kind, text, _ in snippet_parts(snippet):
            if kind != "text":
                continue
            for segment in re.split(r"(`+[^`]*`+)", text):
                if segment.startswith("`"):
                    continue
                for match in _LINK.finditer(segment):
                    destination = _destination(match[2], str(snippet.get("path", "")))
                    if destination:
                        links.setdefault(destination, match[1])
    result = []
    for (path, anchor), label in links.items():
        keys = set()
        for identifier, example in records.items():
            if identifier in invalid or not _verified(example):
                continue
            # The first declared source is the component tutorial's entry.
            # Shared builder/report continuations do not make their book an
            # entry for every tutorial which happens to reuse that host.
            primary = next(iter(example.get("snippets", ())), {})
            if (primary.get("complete") is True and primary.get("path") == path
                    and (not anchor or anchor in _anchors(primary))):
                keys.update(key for key in example.get("component_keys", ())
                            if key != entry_key and identifier in index.get("entries", {}).get(key, ()))
        if keys:
            result.append({"label": label, "path": path, "anchor": anchor, "keys": tuple(sorted(keys))})
    return tuple(result)


def render_documentation_navigation(st: Any, *, entry: Mapping[str, Any], index: Mapping[str, Any],
                                    available_entries: Sequence[Mapping[str, Any]],
                                    on_navigate, navigation_kwargs: Mapping[str, Any]) -> None:
    """Use the existing navigation callback and the caller's scoped entries."""
    available = {row["key"]: row for row in available_entries}
    groups = []
    seen = set()
    for group in documentation_reference_groups(index, str(entry["key"])):
        targets = tuple(available[key] for key in group["keys"] if key in available and key not in seen)
        if targets:
            groups.append((group, targets))
            seen.update(row["key"] for row in targets)
    if not groups:
        return
    st.markdown("**教程中提到的用法**", unsafe_allow_html=False)
    st.caption("以下入口来自本页教程的明确文档链接，用于继续阅读；不表示组件等价或必须配套。")
    for group, targets in groups:
        with st.expander(f"{group['label']} · {len(targets)} 个组件", expanded=True):
            st.caption(group["path"] + ("#" + group["anchor"] if group["anchor"] else ""))
            for row in targets:
                key = row["key"]
                st.button(f"{row.get('title') or key} · {key}",
                          key=f"catalog_ui::tutorial_reference::{entry['key']}::{key}",
                          on_click=on_navigate,
                          kwargs={**navigation_kwargs, "target_key": key,
                                  "target_kind": str(row.get("kind") or ""), "detail_tab": "overview"})


__all__ = ["documentation_reference_groups", "render_documentation_navigation"]
