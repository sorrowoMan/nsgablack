"""Extract a complete manual guide as reference material, never as approval.

The input is the ordinary Catalog example list, not a clipped source-pack
excerpt.  Selection follows the same rule as the component page.  Extraction
is intentionally conservative: missing prose, incomplete fences and placeholder
code return ``None`` rather than being filled with invented instructions.
Nothing here imports, executes, repairs or generates the documented API.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .usage_learning import documentation_fields, select_documentation_guide


_LABELS = ("什么时候用", "先准备什么", "放在哪", "接入步骤", "怎样判断接对", "运行入口")
_VARIANT = re.compile(r"^ {0,3}###\s+((?:变体|变化用法|延拓用法)[^\n]*)$")
_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})([^`]*)$")
_PLACEHOLDER = re.compile(
    r"结果检查说明待补|尚未提供可照做的结果检查|结果待补|待补充|待完善|"
    r"\bTODO\b|\bTBD\b|得到已装配组件或回调返回值|"
    r"同一正式\s*Case\s*已构造的\s*solver\s*与问题候选管线",
    re.IGNORECASE,
)
_TRUNCATED = re.compile(
    r"\[\s*(?:\.\.\.|…)?\s*truncated\b[^\]]*\]|"
    r"\b(?:output|content|source|excerpt)\s+(?:was\s+)?truncated\b|"
    r"(?:内容|源码|片段|摘录|输出)(?:已|被)?截断|截断标记",
    re.IGNORECASE,
)


class _IncompleteGuide(ValueError):
    pass


def _closing(line: str, fence: str) -> bool:
    return bool(re.fullmatch(r" {0,3}" + re.escape(fence[0])
                             + "{" + str(len(fence)) + r",}\s*", line))


def _sections(text: str) -> list[tuple[str | None, str, int]]:
    """Keep exact Markdown; only real, unfenced variant headings split it."""
    sections: list[tuple[str | None, str, int]] = []
    lines = text.splitlines(keepends=True)
    fence, title, start = None, None, 0
    for index, line in enumerate(lines):
        plain = line.rstrip("\r\n")
        if fence is not None:
            if _closing(plain, fence):
                fence = None
            continue
        opening = _OPEN.fullmatch(plain)
        if opening:
            fence = opening[1]
            continue
        match = _VARIANT.fullmatch(plain)
        if match:
            sections.append((title, "".join(lines[start:index]), start))
            title, start = match[1].strip(), index
        elif title is not None and re.match(r"^ {0,3}#{1,3}\s", plain):
            sections.append((title, "".join(lines[start:index]), start))
            title, start = None, index
    if fence is not None:
        raise _IncompleteGuide("unclosed code fence")
    sections.append((title, "".join(lines[start:]), start))
    return sections


def _parts(markdown: str, *, path: str, start_line: int,
           file_sha256: str | None) -> list[dict[str, Any]]:
    """Preserve source order, exact block contents and their original location."""
    result: list[dict[str, Any]] = []
    lines = markdown.splitlines(keepends=True)
    fence, language, start = None, None, 0
    for index, line in enumerate(lines):
        plain = line.rstrip("\r\n")
        if fence is None:
            opening = _OPEN.fullmatch(plain)
            if not opening:
                continue
            if index > start:
                result.append({"kind": "text", "text": "".join(lines[start:index]),
                               "path": path, "start_line": start_line + start,
                               "end_line": start_line + index - 1,
                               "file_sha256": file_sha256})
            fence = opening[1]
            info = opening[2].strip().split()
            language = info[0].lower() if info else None
            language = {"py": "python", "sh": "bash", "shell": "bash",
                        "console": "bash"}.get(language, language)
            start = index + 1
        elif _closing(plain, fence):
            result.append({"kind": "code", "text": "".join(lines[start:index]),
                           "language": language, "path": path,
                           "start_line": start_line + start,
                           "end_line": start_line + index - 1,
                           "file_sha256": file_sha256})
            fence, language, start = None, None, index + 1
    if fence is not None:
        raise _IncompleteGuide("unclosed code fence")
    if start < len(lines):
        result.append({"kind": "text", "text": "".join(lines[start:]),
                       "path": path, "start_line": start_line + start,
                       "end_line": start_line + len(lines) - 1,
                       "file_sha256": file_sha256})
    return result


def _python_blocks(parts: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    blocks = [part for part in parts
              if part["kind"] == "code" and part.get("language") == "python"]
    if not blocks:
        raise _IncompleteGuide("no Python code")
    substantive = False
    for part in blocks:
        tree = ast.parse(part["text"])
        if any(isinstance(node, ast.Constant) and node.value is Ellipsis
               for node in ast.walk(tree)):
            raise _IncompleteGuide("placeholder Python")
        substantive |= any(not isinstance(node, (ast.Import, ast.ImportFrom, ast.Pass))
                           and not (isinstance(node, ast.Expr)
                                    and isinstance(node.value, ast.Constant)
                                    and isinstance(node.value.value, str))
                           for node in tree.body)
    if not substantive:
        raise _IncompleteGuide("imports alone are not an example")
    return blocks


def _content(markdown: str, parts: list[dict[str, Any]]) -> dict[str, Any]:
    blocks = _python_blocks(parts)
    # This is an ordered editorial reference, not a single executable module:
    # imports and relative imports may belong to different files.  The original
    # file comments and intervening instructions remain in fragments/parts.
    code = "\n\n".join(
        f"# Source guide: {part['path']}:{part['start_line']}\n{part['text']}"
        for part in blocks
    )
    return {"markdown": markdown, "parts": parts,
            "code_fragments": [dict(part) for part in blocks],
            "code": code, "language": "python", "code_is_multi_fragment": True}


def extract_source_guide_seed(examples: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Return a faithful, complete manual reference or ``None``.

    All six explicit teaching fields, syntactically complete substantive Python
    main code and at least one prose-backed Python variant are required.  A
    snippet must explicitly carry ``complete=True``; an evidence excerpt with a
    truncation marker cannot qualify even if its visible fences happen to close.

    A returned seed is *not* a publishable tutorial or behavioral verification.
    It still requires faithful model rewriting or independent source review.
    Unknown behavior and runtime correctness are deliberately not inferred.
    """
    guide = select_documentation_guide(examples)
    if guide is None or guide.get("usage_status") == "migration_reference":
        return None
    snippets = guide.get("snippets", ())
    if not snippets or any(not isinstance(item, Mapping) or item.get("complete") is not True
                           for item in snippets):
        return None
    fields = documentation_fields(snippets)
    if any(not fields.get(label) for label in _LABELS):
        return None
    text = "\n\n".join(str(item.get("text", "")) for item in snippets)
    if _PLACEHOLDER.search(text) or _TRUNCATED.search(text):
        return None
    main_markdown: list[str] = []
    main_parts: list[dict[str, Any]] = []
    variants: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    try:
        for snippet in snippets:
            path = str(snippet.get("path", ""))
            if not path.lower().endswith((".md", ".rst")):
                raise _IncompleteGuide("not a documentation source")
            first_line = int(snippet.get("start_line", 1))
            sources.append({key: snippet[key] for key in (
                "path", "start_line", "end_line", "sha256", "file_sha256") if key in snippet})
            for title, markdown, offset in _sections(str(snippet["text"])):
                parts = _parts(markdown, path=path, start_line=first_line + offset,
                               file_sha256=snippet.get("file_sha256"))
                if title is None:
                    main_markdown.append(markdown)
                    main_parts.extend(parts)
                    continue
                # Heading-only, code-only and prose-only variants are not a
                # usable extension.  Instructions on either side stay intact.
                prose = "\n".join(part["text"] for part in parts if part["kind"] == "text")
                prose = re.sub(r"^ {0,3}###[^\n]*", "", prose, count=1).strip()
                if len(re.sub(r"\s", "", prose)) < 20:
                    raise _IncompleteGuide("variant lacks instructions")
                variants.append({"title": title, **_content(markdown, parts)})
        if not variants:
            return None
        main = _content("\n\n".join(main_markdown), main_parts)
        main["fields"] = {label: list(fields[label]) for label in _LABELS}
        # Identical code with a new heading does not establish a real variant.
        baseline = {part["text"].strip() for part in main["code_fragments"]}
        if any(all(part["text"].strip() in baseline for part in variant["code_fragments"])
               for variant in variants):
            return None
    except (SyntaxError, ValueError, TypeError, KeyError):
        return None
    return {"schema": "catalog.source_guide_seed/v1", "reference_only": True,
            "requires_generation_or_independent_review": True,
            "example_id": str(guide.get("id", "")),
            "source_digest": guide.get("source_digest"), "sources": sources,
            "main": main, "variants": variants}


def _covered_part(part: Mapping[str, Any], evidence: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """A whole part must occur at its declared lines inside one original excerpt."""
    start, end = part.get("start_line"), part.get("end_line")
    digest = part.get("file_sha256")
    if not digest or type(start) is not int or type(end) is not int or not 0 < start <= end:
        return None
    for item in evidence:
        if not isinstance(item, Mapping):
            continue
        first, last = item.get("start_line"), item.get("end_line")
        if (item.get("path") != part.get("path") or item.get("file_sha256") != digest
                or type(first) is not int or type(last) is not int
                or not first <= start <= end <= last
                or not isinstance(item.get("text"), str)
                or not isinstance(item.get("id"), str) or not item["id"]):
            continue
        lines = item["text"].splitlines(keepends=True)
        selected = "".join(lines[start - first:end - first + 1])
        # The examples index normalizes CRLF and may omit its excerpt's final
        # newline.  Only these line-ending representations may differ.  Return
        # the packet's *literal* lines, never the normalized comparison text.
        expected = str(part.get("text", "")).replace("\r\n", "\n")
        aligned = selected.replace("\r\n", "\n")
        if (aligned == expected
                or (not expected.endswith("\n") and aligned == expected + "\n")):
            return {**part, "text": selected, "evidence_ids": [item["id"]]}
    return None


def _bounded_content(content: Mapping[str, Any], evidence: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    parts = [_covered_part(part, evidence) for part in content["parts"]]
    if any(part is None for part in parts):
        return None
    return {"parts": parts, "code_fragments": [part for part in parts
                if part["kind"] == "code" and part.get("language") == "python"]}


def bounded_source_guide_reference(packet: Mapping[str, Any],
                                   examples: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    """Keep main + the first complete variant actually quoted by this packet.

    A full-file digest alone never licenses text outside an evidence excerpt.
    Every prose/code part must match the same path, file digest, exact line
    interval and literal text in one existing evidence item.  No evidence is
    added, no packet identity changes, and no publication approval is implied.
    """
    seed = extract_source_guide_seed(examples)
    if seed is None:
        return None
    evidence = packet.get("evidence", ())
    if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes)):
        return None
    main = _bounded_content(seed["main"], evidence)
    if main is None:
        return None
    variant = None
    for candidate in seed["variants"]:
        bounded = _bounded_content(candidate, evidence)
        if bounded is not None:
            variant = {"title": candidate["title"], **bounded}
            break
    if variant is None:
        return None
    evidence_ids = list(dict.fromkeys(item for section in (main, variant)
                                     for part in section["parts"] for item in part["evidence_ids"]))
    return {"schema": "catalog.bounded_source_guide_reference/v1", "reference_only": True,
            "requires_generation_or_independent_review": True,
            "example_id": seed["example_id"], "source_digest": seed["source_digest"],
            "main": {"fields": seed["main"]["fields"], **main},
            "variants": [variant], "evidence_ids": evidence_ids}


__all__ = ["extract_source_guide_seed", "bounded_source_guide_reference"]
